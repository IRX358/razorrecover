# Closed-loop feedback agent
# Compares predicted vs actual recovery outcomes and recalibrates assumption rates
# when observed drift exceeds the safety threshold

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm import Session
from models import Action, RecoveryPlay, Assumption, CalibrationLog, AuditLog, generate_id

# --- Guardrails ---
MIN_SAMPLE_SIZE = 5       # Need at least 5 executed actions before recalibrating
DRIFT_THRESHOLD = 0.10    # Only act when reality differs by more than 10 percentage points
RATE_FLOOR = 0.05         # Never let a rate collapse to zero (temporary outages happen)
RATE_CEILING = 0.95       # Nothing succeeds 100% of the time
BLEND_NEW = 0.6           # Weight for observed data in the blended update
BLEND_OLD = 0.4           # Weight for the existing assumption (prevents overcorrection)


def run_feedback_loop(db: Session) -> dict:
    """
    Main feedback loop. Aggregates all executed actions by cause_type,
    calculates the realized effectiveness rate, and recalibrates assumptions
    when the drift exceeds our threshold.
    """
    # Grab every action that has a final outcome
    actions = db.query(Action).filter(
        Action.status.in_(["verified", "partial", "failed"])
    ).all()

    if not actions:
        return {"calibrations": 0, "message": "No executed actions to learn from yet"}

    # Group outcomes by the parent play's leak_category
    by_cause = {}
    for action in actions:
        play = db.query(RecoveryPlay).filter(RecoveryPlay.id == action.play_id).first()
        if not play:
            continue

        cause = play.leak_category
        if cause not in by_cause:
            by_cause[cause] = {"total_eligible": 0, "total_recovered": 0, "count": 0}

        by_cause[cause]["total_eligible"] += play.eligible_recovery
        by_cause[cause]["total_recovered"] += action.actual_recovered_amount
        by_cause[cause]["count"] += 1

    calibrations = []

    for cause_type, data in by_cause.items():
        if data["count"] < MIN_SAMPLE_SIZE:
            continue
        if data["total_eligible"] <= 0:
            continue

        # What actually happened vs what the assumption table says
        realized_rate = data["total_recovered"] / data["total_eligible"]
        realized_rate = max(RATE_FLOOR, min(RATE_CEILING, realized_rate))

        assumption = db.query(Assumption).filter(
            Assumption.cause_type == cause_type
        ).first()
        if not assumption:
            continue

        current_rate = assumption.action_effectiveness
        drift = abs(realized_rate - current_rate)

        if drift < DRIFT_THRESHOLD:
            continue

        # Blended update: 60% real data, 40% old assumption
        new_rate = (BLEND_NEW * realized_rate) + (BLEND_OLD * current_rate)
        new_rate = round(max(RATE_FLOOR, min(RATE_CEILING, new_rate)), 4)
        old_rate = current_rate

        # Apply the recalibration
        assumption.action_effectiveness = new_rate
        assumption.source_note = (
            f"{assumption.source_note} | "
            f"Auto-calibrated from {old_rate:.2f} → {new_rate:.2f} "
            f"based on {data['count']} executions (realized: {realized_rate:.2f})"
        )

        # Log the calibration event for transparency
        cal_log = CalibrationLog(
            id=generate_id(),
            cause_type=cause_type,
            field_name="action_effectiveness",
            old_value=old_rate,
            new_value=new_rate,
            realized_rate=round(realized_rate, 4),
            sample_size=data["count"],
            drift=round(drift, 4),
        )
        db.add(cal_log)

        # Immutable audit trail entry
        audit = AuditLog(
            id=generate_id(),
            actor="feedback_agent",
            details_json={
                "event": "assumption_calibrated",
                "cause_type": cause_type,
                "old_rate": old_rate,
                "new_rate": new_rate,
                "realized_rate": round(realized_rate, 4),
                "sample_size": data["count"],
                "drift": round(drift, 4),
            },
        )
        db.add(audit)

        calibrations.append({
            "cause_type": cause_type,
            "old_rate": old_rate,
            "new_rate": new_rate,
            "realized_rate": round(realized_rate, 4),
            "sample_size": data["count"],
            "drift": round(drift, 4),
        })

    db.commit()

    return {
        "calibrations": len(calibrations),
        "details": calibrations,
        "message": f"Feedback loop complete. {len(calibrations)} assumption(s) recalibrated."
    }


def get_calibration_history(db: Session) -> list:
    """Returns all past calibration events for the frontend transparency panel."""
    logs = db.query(CalibrationLog).order_by(CalibrationLog.created_at.desc()).all()
    return [
        {
            "id": log.id,
            "cause_type": log.cause_type,
            "field": log.field_name,
            "old_value": log.old_value,
            "new_value": log.new_value,
            "realized_rate": log.realized_rate,
            "sample_size": log.sample_size,
            "drift": log.drift,
            "timestamp": log.created_at.isoformat() if log.created_at else None,
        }
        for log in logs
    ]
