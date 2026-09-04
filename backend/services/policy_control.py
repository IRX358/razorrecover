# Conversational Policy Control
# Parses merchant intent from natural language and maps it to bounded
# policy toggles that the Reactive Agent reads before acting.
# The LLM never decides eligibility or calculates anything here —
# it only maps intent to a policy key, which this module validates and applies.

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import datetime
import re
from sqlalchemy.orm import Session
from models import AgentPolicy, AuditLog, generate_id

# All valid policy keys the system recognizes
VALID_POLICY_KEYS = {
    "reactive_agent.master_active",
    "auto_retry.upi_timeout",
    "auto_retry.gateway_error",
    "auto_retry.card_decline",
    "auto_route_change.card_decline",
    "auto_capture_payment.uncaptured",
    "auto_escalate_to_razorpay.settlement_delay",
    "auto_contest_with_evidence.dispute",
    "auto_investigate_product.refund_surge",
}

# Patterns for intent detection (checked before LLM call for speed)
DISABLE_PATTERNS = [
    r"(?:turn off|disable|stop|pause|block|deactivate)\s+(?:auto[- ]?)?(\w[\w\s]*)",
    r"(?:don'?t|do not|never)\s+(?:auto[- ]?)?(\w[\w\s]*)",
]
ENABLE_PATTERNS = [
    r"(?:turn on|enable|start|resume|activate|allow)\s+(?:auto[- ]?)?(\w[\w\s]*)",
]
AMOUNT_PATTERN = r"(?:under|below|less than|max|limit|cap)\s*₹?\s*(\d[\d,]*)"

# Maps natural language fragments to policy keys
INTENT_TO_KEY = {
    "reactive agent": "reactive_agent.master_active",
    "reactive": "reactive_agent.master_active",
    "agent": "reactive_agent.master_active",
    "retry upi": "auto_retry.upi_timeout",
    "retry for upi": "auto_retry.upi_timeout",
    "upi retry": "auto_retry.upi_timeout",
    "upi timeout": "auto_retry.upi_timeout",
    "upi failures": "auto_retry.upi_timeout",
    "retry gateway": "auto_retry.gateway_error",
    "gateway retry": "auto_retry.gateway_error",
    "gateway error": "auto_retry.gateway_error",
    "retry card": "auto_retry.card_decline",
    "card retry": "auto_retry.card_decline",
    "card decline": "auto_retry.card_decline",
    "card failure": "auto_retry.card_decline",
    "route change": "auto_route_change.card_decline",
    "capture payment": "auto_capture_payment.uncaptured",
    "auto capture": "auto_capture_payment.uncaptured",
    "uncaptured": "auto_capture_payment.uncaptured",
    "settlement": "auto_escalate_to_razorpay.settlement_delay",
    "dispute": "auto_contest_with_evidence.dispute",
    "refund": "auto_investigate_product.refund_surge",
}


def try_parse_policy_intent(message: str, db: Session) -> dict | None:
    """
    Tries to parse a policy control intent from the merchant's chat message.
    Returns a result dict if a policy action was taken, or None if the message
    isn't a policy command (so the normal copilot can handle it).
    """
    msg_lower = message.lower().strip()

    # Try to detect a disable intent
    for pattern in DISABLE_PATTERNS:
        match = re.search(pattern, msg_lower)
        if match:
            fragment = match.group(1).strip()
            policy_key = _resolve_policy_key(fragment)
            if policy_key:
                amount_cap = _extract_amount(msg_lower)
                return _apply_policy(policy_key, enabled=False, max_amount=amount_cap, db=db, raw_message=message)

    # Try to detect an enable intent
    for pattern in ENABLE_PATTERNS:
        match = re.search(pattern, msg_lower)
        if match:
            fragment = match.group(1).strip()
            policy_key = _resolve_policy_key(fragment)
            if policy_key:
                amount_cap = _extract_amount(msg_lower)
                return _apply_policy(policy_key, enabled=True, max_amount=amount_cap, db=db, raw_message=message)

    # Check for amount-cap-only commands ("only auto-retry UPI under ₹500")
    amount_cap = _extract_amount(msg_lower)
    if amount_cap is not None:
        for fragment, key in INTENT_TO_KEY.items():
            if fragment in msg_lower:
                return _apply_policy(key, enabled=True, max_amount=amount_cap, db=db, raw_message=message)

    # Check for a "pause the HDFC play" style command
    if "pause" in msg_lower:
        for fragment, key in INTENT_TO_KEY.items():
            if fragment in msg_lower:
                return _apply_policy(key, enabled=False, max_amount=None, db=db, raw_message=message)

    return None


def _resolve_policy_key(fragment: str) -> str | None:
    """Maps a natural language fragment to a valid policy key."""
    fragment = fragment.strip().rstrip("s")  # normalize plurals
    for keyword, key in INTENT_TO_KEY.items():
        if keyword in fragment or fragment in keyword:
            return key
    return None


def _extract_amount(text: str) -> float | None:
    """Pulls an amount cap from text like 'under ₹500' or 'below 2,000'."""
    match = re.search(AMOUNT_PATTERN, text)
    if match:
        raw = match.group(1).replace(",", "")
        try:
            return float(raw)
        except ValueError:
            return None
    return None


def _apply_policy(policy_key: str, enabled: bool, max_amount: float | None,
                   db: Session, raw_message: str) -> dict:
    """Creates or updates a policy record and logs the change."""
    policy = db.query(AgentPolicy).filter(AgentPolicy.policy_key == policy_key).first()

    old_state = None
    if policy:
        old_state = {"enabled": policy.enabled, "max_amount": policy.max_amount}
        policy.enabled = enabled
        if max_amount is not None:
            policy.max_amount = max_amount
        policy.updated_by = "copilot"
        policy.updated_at = datetime.datetime.now(datetime.UTC)
    else:
        action_desc = policy_key.replace(".", " → ").replace("_", " ").title()
        policy = AgentPolicy(
            id=generate_id(),
            policy_key=policy_key,
            enabled=enabled,
            max_amount=max_amount,
            description=f"Controls whether the agent can auto-{action_desc}",
            updated_by="copilot",
        )
        db.add(policy)

    # Audit trail
    audit = AuditLog(
        id=generate_id(),
        actor="copilot_policy_control",
        details_json={
            "policy_key": policy_key,
            "action": "enabled" if enabled else "disabled",
            "max_amount": max_amount,
            "old_state": old_state,
            "raw_message": raw_message,
        },
    )
    db.add(audit)
    db.commit()

    # Build a human-readable confirmation
    status_word = "enabled" if enabled else "disabled"
    cap_note = f" with amount cap ₹{max_amount:,.0f}" if max_amount is not None else ""
    readable_key = policy_key.replace(".", " → ").replace("_", " ")

    return {
        "type": "policy_update",
        "policy_key": policy_key,
        "enabled": enabled,
        "max_amount": max_amount,
        "confirmation": f"✅ Policy **{readable_key}** has been **{status_word}**{cap_note}. This takes effect immediately for all future webhook events.",
    }


def get_all_policies(db: Session) -> list:
    """Returns all configured agent policies for the dashboard."""
    policies = db.query(AgentPolicy).order_by(AgentPolicy.policy_key).all()
    return [
        {
            "id": p.id,
            "policy_key": p.policy_key,
            "enabled": p.enabled,
            "max_amount": p.max_amount,
            "description": p.description,
            "updated_by": p.updated_by,
            "updated_at": p.updated_at.isoformat() if p.updated_at else None,
        }
        for p in policies
    ]


def seed_default_policies(db: Session):
    """Creates default policies if none exist (called once during startup or seed)."""
    existing = db.query(AgentPolicy).count()
    if existing > 0:
        return

    defaults = [
        ("auto_retry.upi_timeout", True, 5000, "Auto-retry UPI timeouts up to ₹5,000"),
        ("auto_retry.gateway_error", True, 5000, "Auto-retry gateway errors up to ₹5,000"),
        ("auto_retry.card_decline", False, None, "Auto-retry card declines (disabled by default — needs route change)"),
        ("auto_route_change.card_decline", True, 10000, "Auto route-change for card declines up to ₹10,000"),
        ("auto_capture_payment.uncaptured", True, None, "Auto-capture authorized payments nearing expiry"),
        ("auto_escalate_to_razorpay.settlement_delay", True, None, "Auto-escalate settlement delays to Razorpay"),
        ("auto_contest_with_evidence.dispute", False, None, "Auto-contest disputes (disabled — legal implications)"),
        ("auto_investigate_product.refund_surge", False, None, "Auto-investigate refund surges (disabled by default)"),
    ]
    for key, enabled, max_amt, desc in defaults:
        db.add(AgentPolicy(
            id=generate_id(), policy_key=key, enabled=enabled,
            max_amount=max_amt, description=desc, updated_by="system",
        ))
    db.commit()
