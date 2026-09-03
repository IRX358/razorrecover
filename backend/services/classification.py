# Deterministic 2D classification engine (zero AI)
# Maps payments to (transaction_state, recovery_status, leak_category)

import datetime
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm import Session
from models import Payment, Refund, Settlement, Dispute, RevenueClassification


# Error reasons that indicate transient or route-changeable failures
RETRYABLE_ERRORS = {
    "upi_timeout",
    "payment_failed",
    "gateway_error",
    "server_error",
    "gateway_timeout",
    "card_declined",
    "card_declined_risk",
}

# Error reason to leak category mapping
ERROR_TO_LEAK = {
    "upi_timeout": "upi_timeout",
    "payment_failed": "card_decline",
    "gateway_error": "gateway_error",
    "server_error": "gateway_error",
    "gateway_timeout": "gateway_error",
    "card_declined": "card_decline",
    "card_declined_risk": "card_decline",
}

# Settlement SLA threshold: T+2 business days
SETTLEMENT_SLA_DAYS = 3


def classify_single_payment(
    payment: Payment,
    refunds: list,
    settlements: list,
    disputes: list
) -> dict:
    now = datetime.datetime.now(datetime.UTC)
    amount = payment.amount or 0.0

    # 1. Dispute rules (highest priority)
    open_disputes = [d for d in disputes if d.status == "open"]
    if open_disputes:
        dispute = open_disputes[0]
        if dispute.respond_by and dispute.respond_by.replace(tzinfo=datetime.UTC if dispute.respond_by.tzinfo is None else dispute.respond_by.tzinfo) > now:
            # open dispute still within evidence window
            return {
                "payment_id": payment.id,
                "transaction_state": "DISPUTED",
                "recovery_status": "ELIGIBLE",
                "leak_category": "dispute",
                "amount": dispute.amount or amount,
            }
        else:
            # open dispute but deadline has passed
            return {
                "payment_id": payment.id,
                "transaction_state": "DISPUTED",
                "recovery_status": "NOT_ELIGIBLE",
                "leak_category": "dispute",
                "amount": dispute.amount or amount,
            }

    resolved_disputes = [d for d in disputes if d.status in ("won", "lost", "closed")]
    if resolved_disputes:
        return {
            "payment_id": payment.id,
            "transaction_state": "DISPUTED",
            "recovery_status": "NOT_APPLICABLE",
            "leak_category": None,
            "amount": amount,
        }

    # 2. Refund rules
    processed_refunds = [r for r in refunds if r.status == "processed"]
    if processed_refunds:
        return {
            "payment_id": payment.id,
            "transaction_state": "REFUNDED",
            "recovery_status": "NOT_ELIGIBLE",
            "leak_category": "refund_surge",
            "amount": sum(r.amount for r in processed_refunds),
        }

    # 3. Captured and settlement SLA checks
    if payment.status == "captured" or payment.captured:
        processed_settlements = [s for s in settlements if s.status == "processed"]
        if processed_settlements:
            return {
                "payment_id": payment.id,
                "transaction_state": "SETTLED",
                "recovery_status": "NOT_APPLICABLE",
                "leak_category": None,
                "amount": amount,
            }

        created = payment.created_at
        if created and hasattr(created, 'replace'):
            created_aware = created.replace(tzinfo=datetime.UTC) if created.tzinfo is None else created
        else:
            created_aware = now

        days_since = (now - created_aware).days

        if days_since > SETTLEMENT_SLA_DAYS:
            # settlement delayed past T+2 SLA
            return {
                "payment_id": payment.id,
                "transaction_state": "CAPTURED",
                "recovery_status": "ELIGIBLE",
                "leak_category": "settlement_delay",
                "amount": amount,
            }
        else:
            # within normal settlement SLA window
            return {
                "payment_id": payment.id,
                "transaction_state": "CAPTURED",
                "recovery_status": "NOT_APPLICABLE",
                "leak_category": None,
                "amount": amount,
            }

    # 4. Authorized but uncaptured payments
    if payment.status == "authorized" and not payment.captured:
        created = payment.created_at
        if created and hasattr(created, 'replace'):
            created_aware = created.replace(tzinfo=datetime.UTC) if created.tzinfo is None else created
        else:
            created_aware = now
        hours_since = (now - created_aware).total_seconds() / 3600

        if hours_since > 20:
            return {
                "payment_id": payment.id,
                "transaction_state": "AUTHORIZED",
                "recovery_status": "ELIGIBLE",
                "leak_category": "uncaptured",
                "amount": amount,
            }
        else:
            return {
                "payment_id": payment.id,
                "transaction_state": "AUTHORIZED",
                "recovery_status": "NOT_APPLICABLE",
                "leak_category": None,
                "amount": amount,
            }

    # 5. Failed payments (retryable vs terminal)
    if payment.status == "failed":
        error = payment.error_reason or ""
        if error in RETRYABLE_ERRORS:
            leak = ERROR_TO_LEAK.get(error, "gateway_error")
            return {
                "payment_id": payment.id,
                "transaction_state": "FAILED",
                "recovery_status": "ELIGIBLE",
                "leak_category": leak,
                "amount": amount,
            }
        else:
            return {
                "payment_id": payment.id,
                "transaction_state": "FAILED",
                "recovery_status": "NOT_ELIGIBLE",
                "leak_category": "user_abandoned",
                "amount": amount,
            }

    # fallback
    return {
        "payment_id": payment.id,
        "transaction_state": "UNKNOWN",
        "recovery_status": "NOT_APPLICABLE",
        "leak_category": None,
        "amount": amount,
    }


def classify_all(db: Session) -> list:
    db.query(RevenueClassification).delete()

    payments = db.query(Payment).all()
    results = []

    for payment in payments:
        refunds = db.query(Refund).filter(Refund.payment_id == payment.id).all()
        settlements = db.query(Settlement).filter(Settlement.payment_id == payment.id).all()
        disputes = db.query(Dispute).filter(Dispute.payment_id == payment.id).all()

        classification = classify_single_payment(payment, refunds, settlements, disputes)

        rc = RevenueClassification(
            payment_id=classification["payment_id"],
            transaction_state=classification["transaction_state"],
            recovery_status=classification["recovery_status"],
            leak_category=classification["leak_category"],
            amount=classification["amount"],
            state_history=[{
                "state": classification["transaction_state"],
                "recovery": classification["recovery_status"],
                "timestamp": datetime.datetime.now(datetime.UTC).isoformat()
            }],
        )
        db.add(rc)
        results.append(classification)

    db.commit()
    return results


def get_summary(db: Session) -> dict:
    all_rc = db.query(RevenueClassification).all()

    total_payments = len(all_rc)
    revenue_at_risk = sum(rc.amount for rc in all_rc if rc.recovery_status in ("ELIGIBLE", "NOT_ELIGIBLE"))
    recoverable_revenue = sum(rc.amount for rc in all_rc if rc.recovery_status == "ELIGIBLE")

    by_state = {}
    by_recovery = {}
    by_leak = {}
    for rc in all_rc:
        by_state[rc.transaction_state] = by_state.get(rc.transaction_state, 0) + 1
        by_recovery[rc.recovery_status] = by_recovery.get(rc.recovery_status, 0) + 1
        if rc.leak_category:
            by_leak[rc.leak_category] = by_leak.get(rc.leak_category, 0) + 1

    return {
        "total_payments": total_payments,
        "revenue_at_risk": round(revenue_at_risk, 2),
        "recoverable_revenue": round(recoverable_revenue, 2),
        "by_state": by_state,
        "by_recovery_status": by_recovery,
        "by_leak_category": by_leak,
    }
