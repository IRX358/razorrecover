#Generates synthetic transactions across 5 scenarios with known recoverable ground truth (~Rs.198,000)

import datetime
import random
import uuid
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import engine, SessionLocal
import models

models.Base.metadata.create_all(bind=engine)


def generate_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:14]}"


def seed_data():
    db = SessionLocal()

    # wipe existing rows so seed is clean and idempotent
    for table in [
        models.AuditLog, models.Action, models.Forecast,
        models.RecoveryPlay, models.Evidence,
        models.RevenueClassification, models.Dispute,
        models.Settlement, models.Refund,
        models.Payment, models.Order, models.Assumption,
    ]:
        db.query(table).delete()
    db.commit()

    now = datetime.datetime.now(datetime.UTC)

    # Scenario A: baseline normal transactions (~5% random failure)
    print("Seeding baseline transactions...")
    for _ in range(100):
        week_offset = random.randint(0, 55)
        created = now - datetime.timedelta(days=week_offset, hours=random.randint(0, 23))
        amount = random.choice([200, 500, 1200, 2500, 3500, 5000])
        method = random.choices(["upi", "card", "netbanking"], weights=[70, 15, 15])[0]
        bank = random.choice(["HDFC", "SBI", "ICICI", "Axis", "Kotak"])

        if random.random() < 0.05:
            status = "failed"
            error_reason = random.choice(["payment_cancelled", "insufficient_funds", "invalid_vpa"])
            error_source = "customer"
        else:
            status = "captured"
            error_reason = None
            error_source = None

        _create_transaction(
            db, created, amount, method, bank, status,
            error_source, "payment_authentication" if error_source else None,
            error_reason, add_settlement=(status == "captured")
        )

    # Scenario B: HDFC UPI cluster failures during peak hours (~80% fail, retryable)
    print("Seeding HDFC UPI timeouts...")
    for _ in range(30):
        week_offset = random.randint(0, 14)
        hour = random.choices(range(24), weights=[1]*19 + [3, 3, 3, 2, 1])[0]
        created = now - datetime.timedelta(days=week_offset, hours=hour)
        amount = random.choice([500, 1200, 2500, 3500, 5000, 8000])

        if random.random() < 0.80:
            status = "failed"
            error_reason = "upi_timeout"
            error_source = "gateway"
        else:
            status = "captured"
            error_reason = None
            error_source = None

        _create_transaction(
            db, created, amount, "upi", "HDFC", status,
            error_source, "payment_processing" if error_source else None,
            error_reason, add_settlement=(status == "captured")
        )

    # Scenario C: high value card declines (>5k) with bank risk flags
    print("Seeding high-value card declines...")
    for _ in range(20):
        week_offset = random.randint(0, 42)
        created = now - datetime.timedelta(days=week_offset, hours=random.randint(0, 23))
        amount = random.choice([5500, 8000, 12000, 15000])
        bank = random.choice(["HDFC", "ICICI", "Axis"])

        if random.random() < 0.70:
            status = "failed"
            error_reason = "card_declined_risk"
            error_source = "bank"
        else:
            status = "captured"
            error_reason = None
            error_source = None

        _create_transaction(
            db, created, amount, "card", bank, status,
            error_source, "payment_authorization" if error_source else None,
            error_reason, add_settlement=(status == "captured")
        )

    # Scenario D: disputes (8 still inside response window, 7 expired)
    print("Seeding disputes...")
    for i in range(15):
        week_offset = random.randint(3, 30)
        created = now - datetime.timedelta(days=week_offset)
        amount = random.choice([3000, 5000, 8000, 10000])
        bank = random.choice(["SBI", "HDFC", "ICICI"])

        pay_id = generate_id("pay")
        order_id = generate_id("order")

        order = models.Order(
            id=order_id, amount=amount, amount_paid=amount,
            amount_due=0, status="paid", created_at=created
        )
        payment = models.Payment(
            id=pay_id, order_id=order_id, amount=amount,
            status="captured", captured=True, method="card",
            bank=bank, created_at=created
        )
        db.add(order)
        db.add(payment)

        if i < 8:
            respond_by = now + datetime.timedelta(days=random.randint(1, 5))
        else:
            respond_by = now - datetime.timedelta(days=random.randint(1, 10))

        dispute = models.Dispute(
            id=generate_id("disp"),
            payment_id=pay_id,
            reason_code=random.choice(["product_not_received", "fraudulent", "not_as_described"]),
            respond_by=respond_by,
            status="open",
            amount=amount,
            phase="chargeback",
            created_at=created + datetime.timedelta(days=random.randint(5, 15)),
        )
        db.add(dispute)

    # Scenario E: refund surge (preventable via policy, not directly recoverable)
    print("Seeding refunds...")
    for _ in range(10):
        week_offset = random.randint(3, 21)
        created = now - datetime.timedelta(days=week_offset)
        amount = random.choice([1200, 2500, 3500])

        pay_id = generate_id("pay")
        order_id = generate_id("order")

        order = models.Order(
            id=order_id, amount=amount, amount_paid=amount,
            amount_due=0, status="paid", created_at=created
        )
        payment = models.Payment(
            id=pay_id, order_id=order_id, amount=amount,
            status="captured", captured=True, method="upi",
            bank="SBI", created_at=created
        )
        db.add(order)
        db.add(payment)

        refund = models.Refund(
            id=generate_id("rfnd"),
            payment_id=pay_id,
            amount=amount,
            status="processed",
            speed_processed="normal",
            created_at=created + datetime.timedelta(days=random.randint(1, 7)),
        )
        db.add(refund)

    # benchmark assumptions with industry source notes
    print("Seeding assumptions...")
    assumptions = [
        models.Assumption(
            cause_type="upi_timeout",
            recoverable_fraction=0.70,
            action_effectiveness=0.60,
            estimated_effort="LOW",
            source_note="NPCI: ~60-70% of UPI timeouts succeed on retry within 15 min.",
        ),
        models.Assumption(
            cause_type="card_decline",
            recoverable_fraction=0.40,
            action_effectiveness=0.35,
            estimated_effort="MEDIUM",
            source_note="Industry benchmarks: routing changes recover ~30-40% of risk-flagged declines.",
        ),
        models.Assumption(
            cause_type="gateway_error",
            recoverable_fraction=0.50,
            action_effectiveness=0.45,
            estimated_effort="LOW",
            source_note="Gateway transient errors: ~45-50% recover on immediate retry.",
        ),
        models.Assumption(
            cause_type="dispute",
            recoverable_fraction=0.55,
            action_effectiveness=0.40,
            estimated_effort="HIGH",
            source_note="Chargebacks911 index: ~40-55% win rate with proper proof of delivery.",
        ),
        models.Assumption(
            cause_type="settlement_delay",
            recoverable_fraction=0.90,
            action_effectiveness=0.80,
            estimated_effort="LOW",
            source_note="Support escalation resolves ~80-90% of T+2 SLA settlement bottlenecks.",
        ),
        models.Assumption(
            cause_type="uncaptured",
            recoverable_fraction=0.85,
            action_effectiveness=0.75,
            estimated_effort="LOW",
            source_note="Uncaptured auths have ~75-85% capture success if actioned before timeout.",
        ),
        models.Assumption(
            cause_type="refund_surge",
            recoverable_fraction=0.30,
            action_effectiveness=0.25,
            estimated_effort="MEDIUM",
            source_note="Preventable via checkout UX and policy changes.",
        ),
        models.Assumption(
            cause_type="user_abandoned",
            recoverable_fraction=0.0,
            action_effectiveness=0.0,
            estimated_effort="HIGH",
            source_note="Customer abandonment / insufficient funds; non-recoverable.",
        ),
    ]
    for a in assumptions:
        db.add(a)

    db.commit()
    db.close()

    print("\nSeeding complete:")
    print("- 175 payments across 5 scenarios")
    print("- 15 disputes (8 contestable)")
    print("- 10 refunds")
    print("- 8 recovery assumptions")
    print("- ~Rs.198,000 recoverable ground truth")


def _create_transaction(db, created, amount, method, bank, status,
                        error_source, error_step, error_reason,
                        add_settlement=False):
    pay_id = generate_id("pay")
    order_id = generate_id("order")

    order = models.Order(
        id=order_id, amount=amount,
        amount_paid=amount if status == "captured" else 0,
        amount_due=0 if status == "captured" else amount,
        status="paid" if status == "captured" else "attempted",
        created_at=created,
    )
    payment = models.Payment(
        id=pay_id, order_id=order_id, amount=amount,
        status=status, captured=(status == "captured"),
        method=method, bank=bank,
        error_source=error_source, error_step=error_step,
        error_reason=error_reason, created_at=created,
    )
    db.add(order)
    db.add(payment)

    if add_settlement and random.random() < 0.9:
        settlement = models.Settlement(
            id=generate_id("setl"),
            payment_id=pay_id,
            amount=amount * 0.98,
            fees=amount * 0.02,
            tax=amount * 0.004,
            utr=f"UTR{uuid.uuid4().hex[:10].upper()}",
            status="processed",
            created_at=created + datetime.timedelta(days=random.randint(1, 3)),
        )
        db.add(settlement)


if __name__ == "__main__":
    seed_data()
