from sqlalchemy import Column, String, Float, Integer, ForeignKey, DateTime, JSON, Boolean, Text
from sqlalchemy.orm import relationship
import datetime
import uuid
from database import Base


def generate_id():
    return str(uuid.uuid4())


# Razorpay entities (mirrors webhook / API payloads)

class Payment(Base):
    __tablename__ = "payments"
    id = Column(String, primary_key=True, index=True)
    order_id = Column(String, index=True)
    amount = Column(Float)
    status = Column(String)  # created, authorized, captured, failed, refunded
    captured = Column(Boolean, default=False)
    method = Column(String)  # upi, card, netbanking, wallet
    bank = Column(String, nullable=True)
    error_source = Column(String, nullable=True)  # gateway, bank, customer
    error_step = Column(String, nullable=True)     # auth, authentication, etc.
    error_reason = Column(String, nullable=True)   # upi_timeout, card_declined, etc.
    created_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.UTC))


class Order(Base):
    __tablename__ = "orders"
    id = Column(String, primary_key=True, index=True)
    amount = Column(Float)
    amount_paid = Column(Float, default=0.0)
    amount_due = Column(Float)
    status = Column(String)  # created, attempted, paid
    created_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.UTC))


class Refund(Base):
    __tablename__ = "refunds"
    id = Column(String, primary_key=True, index=True)
    payment_id = Column(String, ForeignKey("payments.id"), index=True)
    amount = Column(Float)
    status = Column(String)  # created, processed, failed
    speed_processed = Column(String, nullable=True)  # normal, instant
    created_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.UTC))


class Settlement(Base):
    __tablename__ = "settlements"
    id = Column(String, primary_key=True, index=True)
    payment_id = Column(String, ForeignKey("payments.id"), index=True, nullable=True)
    amount = Column(Float)
    fees = Column(Float, default=0.0)
    tax = Column(Float, default=0.0)
    utr = Column(String, nullable=True)
    status = Column(String)  # created, processed, failed
    created_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.UTC))


class Dispute(Base):
    __tablename__ = "disputes"
    id = Column(String, primary_key=True, index=True)
    payment_id = Column(String, ForeignKey("payments.id"), index=True)
    reason_code = Column(String, nullable=True)  # chargeback, fraud, etc.
    respond_by = Column(DateTime, nullable=True)
    status = Column(String)  # open, under_review, won, lost, closed
    amount = Column(Float)
    phase = Column(String, nullable=True)  # chargeback, arbitration
    created_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.UTC))


# 2D classification: separates technical payment state from business recoverability
class RevenueClassification(Base):
    __tablename__ = "revenue_classification"
    payment_id = Column(String, ForeignKey("payments.id"), primary_key=True, index=True)
    transaction_state = Column(String)     # FAILED, AUTHORIZED, CAPTURED, SETTLED, REFUNDED, DISPUTED
    recovery_status = Column(String)       # ELIGIBLE, NOT_ELIGIBLE, NOT_APPLICABLE
    leak_category = Column(String, nullable=True)  # upi_timeout, card_decline, settlement_delay, etc.
    amount = Column(Float)
    classified_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.UTC))
    state_history = Column(JSON, default=list)


# Stores anomalous clusters found via z-score detection
class Evidence(Base):
    __tablename__ = "evidence"
    id = Column(String, primary_key=True, default=generate_id)
    segment_key = Column(String, index=True)  # e.g. HDFC_upi or card_high_value
    metric = Column(String, default="failure_rate")
    anomaly_score = Column(Float)        # z-score value
    confidence = Column(Float)           # normalized confidence (0 to 1)
    period = Column(String, nullable=True)
    affected_amount = Column(Float)
    affected_count = Column(Integer)
    created_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.UTC))


# Primary actionable object shown to the merchant
class RecoveryPlay(Base):
    __tablename__ = "recovery_plays"
    id = Column(String, primary_key=True, default=generate_id)
    leak_category = Column(String)
    segment_key = Column(String)
    affected_amount = Column(Float)
    recoverable_fraction = Column(Float)
    eligible_recovery = Column(Float)
    action_effectiveness = Column(Float)
    expected_recovery = Column(Float)
    diagnosis_confidence = Column(Float)
    forecast_confidence = Column(Float, default=0.0)
    recovery_efficiency_score = Column(Float)
    rank_score = Column(Float)
    action_type = Column(String)
    reasoning = Column(Text, default="")   # LLM explanation
    status = Column(String, default="pending")  # pending, executed, resolved, stopped
    created_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.UTC))


# 4-week time-series projection (baseline vs recovery scenario)
class Forecast(Base):
    __tablename__ = "forecasts"
    id = Column(String, primary_key=True, default=generate_id)
    play_id = Column(String, ForeignKey("recovery_plays.id"), index=True)
    horizon_days = Column(Integer, default=28)
    baseline_projection = Column(JSON)     # projected weekly losses if no action
    scenario_projection = Column(JSON)     # projected losses after executing play
    effectiveness_rate_used = Column(Float)
    generated_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.UTC))


# Configurable benchmark rates with citations to prevent magic numbers
class Assumption(Base):
    __tablename__ = "assumptions"
    id = Column(String, primary_key=True, default=generate_id)
    cause_type = Column(String, unique=True, index=True)
    recoverable_fraction = Column(Float)
    action_effectiveness = Column(Float)
    estimated_effort = Column(String)  # LOW, MEDIUM, HIGH
    source_note = Column(Text)
    editable = Column(Boolean, default=True)


# Track idempotent action triggers and execution outcomes
class Action(Base):
    __tablename__ = "actions"
    id = Column(String, primary_key=True, default=generate_id)
    play_id = Column(String, ForeignKey("recovery_plays.id"), index=True)
    type = Column(String)
    status = Column(String, default="pending")  # pending, executed, verified, partial, failed
    idempotency_key = Column(String, unique=True, index=True)
    executed_at = Column(DateTime, nullable=True)
    verified_at = Column(DateTime, nullable=True)
    before_state = Column(String)
    after_state = Column(String, nullable=True)
    actual_recovered_amount = Column(Float, default=0.0)
    created_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.UTC))


# Append-only audit trail
class AuditLog(Base):
    __tablename__ = "audit_log"
    id = Column(String, primary_key=True, default=generate_id)
    actor = Column(String, default="system")
    action_id = Column(String, nullable=True)
    timestamp = Column(DateTime, default=lambda: datetime.datetime.now(datetime.UTC))
    details_json = Column(JSON)


# Records every assumption recalibration by the Feedback Agent
class CalibrationLog(Base):
    __tablename__ = "calibration_logs"
    id = Column(String, primary_key=True, default=generate_id)
    cause_type = Column(String, index=True)
    field_name = Column(String)
    old_value = Column(Float)
    new_value = Column(Float)
    realized_rate = Column(Float)
    sample_size = Column(Integer)
    drift = Column(Float)
    created_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.UTC))


# Records every autonomous decision made by the Reactive Agent
class AgentDecision(Base):
    __tablename__ = "agent_decisions"
    id = Column(String, primary_key=True, default=generate_id)
    payment_id = Column(String, index=True)
    event_type = Column(String)
    tier = Column(Integer)
    decision = Column(String)
    reason = Column(Text)
    action_id = Column(String, nullable=True)
    segment_key = Column(String, nullable=True)
    circuit_breaker_state = Column(String, default="closed")
    created_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.UTC))


# Merchant-configurable policies that govern the Reactive Agent's behavior
# Managed via Copilot chat ("turn off auto-retry for card failures")
class AgentPolicy(Base):
    __tablename__ = "agent_policies"
    id = Column(String, primary_key=True, default=generate_id)
    policy_key = Column(String, unique=True, index=True)  # e.g. "auto_retry.upi_timeout"
    enabled = Column(Boolean, default=True)
    max_amount = Column(Float, nullable=True)              # optional amount cap for this policy
    description = Column(Text, nullable=True)
    updated_by = Column(String, default="system")          # "merchant", "copilot", "system"
    updated_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.UTC))

