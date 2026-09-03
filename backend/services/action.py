# Action execution gateway with safety guardrails
# Ensures idempotency, validates pre-approved actions, and enforces stopping rules

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import hashlib
import random
import datetime
from sqlalchemy.orm import Session
from models import RecoveryPlay, Action, AuditLog, generate_id

# Pre-approved action types allowed to execute
APPROVED_ACTIONS = {"retry", "capture_payment", "contest_with_evidence", "route_change", "escalate_to_razorpay", "investigate_product"}

# Guardrail thresholds
MAX_ATTEMPTS_PER_PLAY = 2
CONFIDENCE_FLOOR = 0.3


def check_eligibility(play: RecoveryPlay, db: Session) -> dict:
    if not play:
        return {"eligible": False, "reason": "Play not found"}

    if play.status != "pending":
        return {"eligible": False, "reason": f"Play already {play.status}"}

    if play.action_type not in APPROVED_ACTIONS:
        return {
            "eligible": False,
            "reason": f"Action type '{play.action_type}' is not pre-approved for execution"
        }

    # 1. Idempotency check: has this exact action already been executed?
    idem_key = _generate_idempotency_key(play)
    existing = db.query(Action).filter(Action.idempotency_key == idem_key).first()
    if existing:
        return {"eligible": False, "reason": "Action already executed (idempotency check)"}

    # 2. Stopping rule: max attempts exhausted
    attempt_count = db.query(Action).filter(Action.play_id == play.id).count()
    if attempt_count >= MAX_ATTEMPTS_PER_PLAY:
        return {"eligible": False, "reason": f"MAX_ATTEMPTS_EXHAUSTED ({attempt_count}/{MAX_ATTEMPTS_PER_PLAY})"}

    # 3. Stopping rule: confidence floor degraded
    if play.diagnosis_confidence < CONFIDENCE_FLOOR:
        return {"eligible": False, "reason": f"CONFIDENCE_DEGRADED (confidence {play.diagnosis_confidence:.2f} < floor {CONFIDENCE_FLOOR})"}

    return {"eligible": True, "reason": "All checks passed"}


def execute_play(play: RecoveryPlay, db: Session) -> dict:
    now = datetime.datetime.now(datetime.UTC)
    idem_key = _generate_idempotency_key(play)

    # In production, calls Razorpay APIs (e.g. POST /v1/payments/{id}/capture)
    # Simulated execution based on action effectiveness
    success_roll = random.random()
    if success_roll < play.action_effectiveness:
        recovered = play.expected_recovery
        status = "verified"
        after_state = "recovered"
    elif success_roll < (play.action_effectiveness + 0.2):
        recovered = play.expected_recovery * random.uniform(0.3, 0.7)
        status = "partial"
        after_state = "partially_recovered"
    else:
        recovered = 0
        status = "failed"
        after_state = "unrecoverable"

    recovered = round(recovered, 2)

    action = Action(
        id=generate_id(),
        play_id=play.id,
        type=play.action_type,
        status=status,
        idempotency_key=idem_key,
        executed_at=now,
        verified_at=now,
        before_state="at_risk",
        after_state=after_state,
        actual_recovered_amount=recovered,
    )
    db.add(action)

    play.status = "executed"

    log_entry = AuditLog(
        id=generate_id(),
        actor="merchant",
        action_id=action.id,
        details_json={
            "play_id": play.id,
            "action_type": play.action_type,
            "segment_key": play.segment_key,
            "expected_recovery": play.expected_recovery,
            "actual_recovered": recovered,
            "outcome": status,
            "idempotency_key": idem_key,
        },
    )
    db.add(log_entry)
    db.commit()

    accuracy = 0
    if play.expected_recovery > 0:
        accuracy = round(recovered / play.expected_recovery * 100, 1)

    return {
        "action_id": action.id,
        "play_id": play.id,
        "action_type": play.action_type,
        "status": status,
        "expected_recovery": play.expected_recovery,
        "actual_recovered": recovered,
        "forecast_accuracy": accuracy,
        "stopping_reason": None if status != "failed" else "ACTION_FAILED",
    }


def _generate_idempotency_key(play: RecoveryPlay) -> str:
    raw = f"{play.id}:{play.action_type}:{play.segment_key}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]
