# Reactive Recovery Agent — real-time autonomous recovery from webhook events
# Monitors incoming payment events, classifies instantly, and acts within
# bounded safety tiers. Every decision is logged for full auditability.

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import datetime
from sqlalchemy.orm import Session
from models import (
    Payment, Order, RecoveryPlay, Action, AgentDecision, AgentPolicy,
    AuditLog, Assumption, Refund, Settlement, Dispute, generate_id
)
from services.classification import classify_single_payment
from services.scoring import LEAK_TO_ACTION
from services.action import check_eligibility, execute_play

# --- Tier thresholds ---
TIER_1_MAX_AMOUNT = 5000
TIER_1_MIN_CONFIDENCE = 0.85
TIER_2_MAX_AMOUNT = 25000
TIER_2_MIN_CONFIDENCE = 0.60

# --- Circuit breaker ---
CB_WINDOW_MINUTES = 10
CB_THRESHOLD = 0.90
MAX_AUTO_RETRIES = 3

# Errors that are safe to auto-retry
AUTO_RETRYABLE = {"upi_timeout", "gateway_error", "server_error", "gateway_timeout"}

# Errors where retrying will never work
TERMINAL_ERRORS = {"user_cancelled", "insufficient_funds", "invalid_vpa", "payment_cancelled"}


def is_agent_enabled(db: Session) -> bool:
    """Checks the master toggle for the Reactive Agent."""
    policy = db.query(AgentPolicy).filter(AgentPolicy.policy_key == "reactive_agent.master_active").first()
    if policy is not None:
        return policy.enabled
    return True


def set_agent_enabled(enabled: bool, db: Session, updated_by: str = "merchant") -> bool:
    """Toggles or sets the master state for the Reactive Agent and audits the change."""
    policy = db.query(AgentPolicy).filter(AgentPolicy.policy_key == "reactive_agent.master_active").first()
    old_state = policy.enabled if policy else True
    if policy:
        policy.enabled = enabled
        policy.updated_by = updated_by
        policy.updated_at = datetime.datetime.now(datetime.UTC)
    else:
        policy = AgentPolicy(
            id=generate_id(),
            policy_key="reactive_agent.master_active",
            enabled=enabled,
            description="Master kill-switch / activation toggle for the autonomous Reactive Recovery Agent",
            updated_by=updated_by,
        )
        db.add(policy)
    
    audit = AuditLog(
        id=generate_id(),
        actor=f"{updated_by}_agent_toggle",
        details_json={
            "action": "enabled" if enabled else "disabled",
            "old_state": old_state,
            "new_state": enabled,
            "policy_key": "reactive_agent.master_active"
        }
    )
    db.add(audit)
    db.commit()
    return enabled


def handle_webhook_event(payment_id: str, event_type: str, db: Session) -> dict:
    """
    Main entry point called when a webhook event arrives.
    Classifies the payment, determines the autonomy tier, checks policies
    and circuit breakers, then acts accordingly.
    """
    if not is_agent_enabled(db):
        return _record_decision(
            db, payment_id, event_type, tier=0,
            decision="agent_disabled",
            reason="Reactive Agent is toggled OFF by merchant"
        )

    payment = db.query(Payment).filter(Payment.id == payment_id).first()
    if not payment:
        return _record_decision(
            db, payment_id, event_type, tier=0,
            decision="skip", reason="Payment not found in database"
        )

    # Classify this single payment through the existing 2D engine
    refunds = db.query(Refund).filter(Refund.payment_id == payment_id).all()
    settlements = db.query(Settlement).filter(Settlement.payment_id == payment_id).all()
    disputes = db.query(Dispute).filter(Dispute.payment_id == payment_id).all()
    classification = classify_single_payment(payment, refunds, settlements, disputes)

    # Not recoverable — nothing to do
    if classification["recovery_status"] != "ELIGIBLE":
        return _record_decision(
            db, payment_id, event_type, tier=0,
            decision="skip",
            reason=f"Not recoverable: {classification['transaction_state']} / {classification['recovery_status']}"
        )

    # Terminal error — retrying won't help
    if payment.error_reason in TERMINAL_ERRORS:
        return _record_decision(
            db, payment_id, event_type, tier=0,
            decision="skip",
            reason=f"Terminal error: {payment.error_reason} — no viable recovery action"
        )

    segment_key = f"{payment.bank or 'unknown'}_{payment.method or 'unknown'}"
    leak_category = classification.get("leak_category", "gateway_error")
    action_type = LEAK_TO_ACTION.get(leak_category, "retry")

    # Check merchant policy — they may have disabled auto-actions for this type
    policy_key = f"auto_{action_type}.{leak_category}"
    policy = db.query(AgentPolicy).filter(AgentPolicy.policy_key == policy_key).first()
    if policy and not policy.enabled:
        return _record_decision(
            db, payment_id, event_type, tier=0,
            decision="policy_blocked",
            reason=f"Merchant policy '{policy_key}' is disabled",
            segment_key=segment_key
        )

    # Check amount cap from policy if set
    amount = payment.amount or 0
    if policy and policy.max_amount is not None and amount > policy.max_amount:
        return _record_decision(
            db, payment_id, event_type, tier=0,
            decision="policy_blocked",
            reason=f"Amount ₹{amount:,.0f} exceeds policy cap of ₹{policy.max_amount:,.0f} for '{policy_key}'",
            segment_key=segment_key
        )

    # Circuit breaker check
    cb_state = _check_circuit_breaker(segment_key, db)
    if cb_state == "open":
        return _record_decision(
            db, payment_id, event_type, tier=0,
            decision="suppress",
            reason=f"Circuit breaker OPEN for {segment_key} — bank infra likely degraded",
            segment_key=segment_key, circuit_breaker_state="open"
        )

    # Retry cap across all time for this payment
    past_auto = db.query(AgentDecision).filter(
        AgentDecision.payment_id == payment_id,
        AgentDecision.decision == "auto_execute"
    ).count()
    if past_auto >= MAX_AUTO_RETRIES:
        return _record_decision(
            db, payment_id, event_type, tier=0,
            decision="suppress",
            reason=f"Max auto-retries ({past_auto}/{MAX_AUTO_RETRIES}) exhausted for this payment",
            segment_key=segment_key
        )

    # Determine confidence and tier
    confidence = _estimate_confidence(payment)
    tier, decision = _determine_tier(amount, confidence)

    if tier == 1:
        return _auto_execute(payment, leak_category, action_type, confidence, segment_key, cb_state, db)
    elif tier == 2:
        _create_recommendation(payment, leak_category, action_type, confidence, segment_key, db)
        return _record_decision(
            db, payment_id, event_type, tier=2,
            decision="recommend",
            reason=f"Tier 2: amount ₹{amount:,.0f} or confidence {confidence:.2f} in mid-range — play created for merchant review",
            segment_key=segment_key, circuit_breaker_state=cb_state
        )
    else:
        return _record_decision(
            db, payment_id, event_type, tier=3,
            decision="escalate",
            reason=f"Tier 3: amount ₹{amount:,.0f} exceeds auto threshold or confidence {confidence:.2f} too low — requires merchant approval",
            segment_key=segment_key, circuit_breaker_state=cb_state
        )


def _determine_tier(amount: float, confidence: float) -> tuple:
    if amount <= TIER_1_MAX_AMOUNT and confidence >= TIER_1_MIN_CONFIDENCE:
        return 1, "auto_execute"
    elif amount <= TIER_2_MAX_AMOUNT and confidence >= TIER_2_MIN_CONFIDENCE:
        return 2, "recommend"
    else:
        return 3, "escalate"


def _estimate_confidence(payment: Payment) -> float:
    """Heuristic confidence for a single payment (batch pipeline uses z-scores instead)."""
    error = payment.error_reason or ""
    confidence_map = {
        "upi_timeout": 0.90,
        "gateway_timeout": 0.90,
        "gateway_error": 0.80,
        "server_error": 0.80,
        "card_declined": 0.65,
        "card_declined_risk": 0.65,
        "payment_failed": 0.55,
    }
    return confidence_map.get(error, 0.40)


def _check_circuit_breaker(segment_key: str, db: Session) -> str:
    """If 90%+ of recent decisions for this segment were failures, halt everything."""
    cutoff = datetime.datetime.now(datetime.UTC) - datetime.timedelta(minutes=CB_WINDOW_MINUTES)
    recent = db.query(AgentDecision).filter(
        AgentDecision.segment_key == segment_key,
        AgentDecision.created_at >= cutoff
    ).all()

    if len(recent) < 3:
        return "closed"

    bad = sum(1 for d in recent if d.decision in ("suppress", "failed"))
    return "open" if (bad / len(recent)) >= CB_THRESHOLD else "closed"


def _auto_execute(payment, leak_category, action_type, confidence, segment_key, cb_state, db):
    """Tier 1: create a mini-play and execute it immediately through the gated gateway."""
    assumption = db.query(Assumption).filter(Assumption.cause_type == leak_category).first()
    rf = assumption.recoverable_fraction if assumption else 0.5
    ae = assumption.action_effectiveness if assumption else 0.4

    amount = payment.amount or 0
    eligible = round(amount * rf, 2)
    expected = round(eligible * ae, 2)

    play = RecoveryPlay(
        id=generate_id(), leak_category=leak_category, segment_key=segment_key,
        affected_amount=amount, recoverable_fraction=rf, eligible_recovery=eligible,
        action_effectiveness=ae, expected_recovery=expected,
        diagnosis_confidence=confidence, forecast_confidence=0.0,
        recovery_efficiency_score=expected, rank_score=confidence,
        action_type=action_type,
        reasoning=f"Auto-generated by Reactive Agent (Tier 1) for {payment.id}",
        status="pending",
    )
    db.add(play)
    db.commit()

    eligibility = check_eligibility(play, db)
    if not eligibility["eligible"]:
        return _record_decision(
            db, payment.id, "payment.failed", tier=1, decision="suppress",
            reason=f"Tier 1 auto-execute blocked: {eligibility['reason']}",
            segment_key=segment_key, circuit_breaker_state=cb_state
        )

    exec_result = execute_play(play, db)
    return _record_decision(
        db, payment.id, "payment.failed", tier=1, decision="auto_execute",
        reason=f"Tier 1: amount ₹{amount:,.0f} ≤ ₹{TIER_1_MAX_AMOUNT:,}, confidence {confidence:.2f}. Auto-executed {action_type}.",
        action_id=exec_result.get("action_id"),
        segment_key=segment_key, circuit_breaker_state=cb_state
    )


def _create_recommendation(payment, leak_category, action_type, confidence, segment_key, db):
    """Tier 2: create a play for merchant review, don't execute."""
    assumption = db.query(Assumption).filter(Assumption.cause_type == leak_category).first()
    rf = assumption.recoverable_fraction if assumption else 0.5
    ae = assumption.action_effectiveness if assumption else 0.4

    amount = payment.amount or 0
    eligible = round(amount * rf, 2)
    expected = round(eligible * ae, 2)

    play = RecoveryPlay(
        id=generate_id(), leak_category=leak_category, segment_key=segment_key,
        affected_amount=amount, recoverable_fraction=rf, eligible_recovery=eligible,
        action_effectiveness=ae, expected_recovery=expected,
        diagnosis_confidence=confidence, forecast_confidence=0.0,
        recovery_efficiency_score=expected, rank_score=confidence,
        action_type=action_type,
        reasoning=f"Recommended by Reactive Agent (Tier 2) — awaiting merchant approval for {payment.id}",
        status="pending",
    )
    db.add(play)
    db.commit()
    return play.id


def _record_decision(db, payment_id, event_type, tier, decision, reason,
                      action_id=None, segment_key=None, circuit_breaker_state="closed"):
    """Log every agent decision to both the agent_decisions table and the audit trail."""
    record = AgentDecision(
        id=generate_id(), payment_id=payment_id, event_type=event_type,
        tier=tier, decision=decision, reason=reason,
        action_id=action_id, segment_key=segment_key,
        circuit_breaker_state=circuit_breaker_state,
    )
    db.add(record)

    audit = AuditLog(
        id=generate_id(), actor="reactive_agent",
        details_json={
            "payment_id": payment_id, "event_type": event_type,
            "tier": tier, "decision": decision, "reason": reason,
            "action_id": action_id, "circuit_breaker": circuit_breaker_state,
        },
    )
    db.add(audit)
    db.commit()

    return {
        "decision_id": record.id, "payment_id": payment_id,
        "event_type": event_type, "tier": tier, "decision": decision,
        "reason": reason, "action_id": action_id,
        "circuit_breaker_state": circuit_breaker_state,
    }


def get_agent_activity(db: Session, limit: int = 50) -> list:
    """Returns recent agent decisions for the dashboard activity feed."""
    decisions = db.query(AgentDecision).order_by(AgentDecision.created_at.desc()).limit(limit).all()
    return [
        {
            "id": d.id, "payment_id": d.payment_id, "event_type": d.event_type,
            "tier": d.tier, "decision": d.decision, "reason": d.reason,
            "action_id": d.action_id, "segment_key": d.segment_key,
            "circuit_breaker_state": d.circuit_breaker_state,
            "timestamp": d.created_at.isoformat() if d.created_at else None,
        }
        for d in decisions
    ]
