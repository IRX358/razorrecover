# Calculates recovery yield based on transparent assumption rates
# Eligible Recovery = affected_amount * recoverable_fraction
# Expected Recovery = eligible_recovery * action_effectiveness

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm import Session
from models import Assumption

# Maps leak category to default recovery play action
LEAK_TO_ACTION = {
    "upi_timeout": "retry",
    "card_decline": "route_change",
    "gateway_error": "retry",
    "settlement_delay": "escalate_to_razorpay",
    "dispute": "contest_with_evidence",
    "uncaptured": "capture_payment",
    "refund_surge": "investigate_product",
    "user_abandoned": "none",
}


def calculate_recovery(evidence_entry: dict, db: Session) -> dict:
    leak_category = evidence_entry.get("leak_category")

    if not leak_category:
        seg = evidence_entry.get("segment_key", "").lower()
        if "upi" in seg:
            leak_category = "upi_timeout"
        elif "card" in seg:
            leak_category = "card_decline"
        elif "netbanking" in seg:
            leak_category = "gateway_error"
        else:
            leak_category = "gateway_error"

    assumption = db.query(Assumption).filter(
        Assumption.cause_type == leak_category
    ).first()

    if not assumption:
        recoverable_fraction = 0.3
        action_effectiveness = 0.2
        estimated_effort = "MEDIUM"
        source = "Fallback default"
    else:
        recoverable_fraction = assumption.recoverable_fraction
        action_effectiveness = assumption.action_effectiveness
        estimated_effort = assumption.estimated_effort
        source = assumption.source_note

    affected_amount = evidence_entry.get("affected_amount", 0)
    eligible_recovery = affected_amount * recoverable_fraction
    expected_recovery = eligible_recovery * action_effectiveness

    action_type = LEAK_TO_ACTION.get(leak_category, "investigate")

    return {
        "segment_key": evidence_entry.get("segment_key", ""),
        "leak_category": leak_category,
        "affected_amount": round(affected_amount, 2),
        "recoverable_fraction": recoverable_fraction,
        "eligible_recovery": round(eligible_recovery, 2),
        "action_effectiveness": action_effectiveness,
        "expected_recovery": round(expected_recovery, 2),
        "action_type": action_type,
        "estimated_effort": estimated_effort,
        "diagnosis_confidence": evidence_entry.get("confidence", 0.5),
        "anomaly_score": evidence_entry.get("anomaly_score", 0),
        "source_note": source,
    }


def score_all_evidence(evidence_list: list, db: Session) -> list:
    return [calculate_recovery(e, db) for e in evidence_list]
