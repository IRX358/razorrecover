# Ranks recovery opportunities based on impact, confidence, and operational feasibility
# Combines yield scores and time-series forecasts into actionable RecoveryPlay records

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm import Session
from models import RecoveryPlay, Forecast, generate_id
from services.forecasting import get_weekly_at_risk, forecast_baseline, forecast_scenario

# Feasibility score weights (easier actions rank higher)
EFFORT_TO_FEASIBILITY = {"LOW": 1.0, "MEDIUM": 0.6, "HIGH": 0.3}
EFFORT_TO_WEIGHT = {"LOW": 1, "MEDIUM": 2, "HIGH": 3}


def rank_and_create_plays(scored_evidence: list, db: Session) -> list:
    if not scored_evidence:
        return []

    # Filter out items with no recovery yield
    valid = [e for e in scored_evidence if e.get("expected_recovery", 0) > 0]
    if not valid:
        return []

    max_recovery = max(e["expected_recovery"] for e in valid)

    # Reset old plays and forecasts
    db.query(Forecast).delete()
    db.query(RecoveryPlay).delete()
    db.commit()

    plays = []
    for entry in valid:
        # Balanced formula: 50% recovery amount, 30% anomaly confidence, 20% ease of execution
        normalized_impact = entry["expected_recovery"] / max_recovery if max_recovery > 0 else 0
        feasibility = EFFORT_TO_FEASIBILITY.get(entry.get("estimated_effort", "MEDIUM"), 0.5)
        confidence = entry.get("diagnosis_confidence", 0.5)

        rank_score = (
            0.5 * normalized_impact +
            0.3 * confidence +
            0.2 * feasibility
        )

        effort_weight = EFFORT_TO_WEIGHT.get(entry.get("estimated_effort", "MEDIUM"), 2)
        efficiency = entry["expected_recovery"] / effort_weight

        play = RecoveryPlay(
            id=generate_id(),
            leak_category=entry.get("leak_category", "unknown"),
            segment_key=entry.get("segment_key", "unknown"),
            affected_amount=entry["affected_amount"],
            recoverable_fraction=entry["recoverable_fraction"],
            eligible_recovery=entry["eligible_recovery"],
            action_effectiveness=entry["action_effectiveness"],
            expected_recovery=entry["expected_recovery"],
            diagnosis_confidence=round(confidence, 3),
            forecast_confidence=0.0,
            recovery_efficiency_score=round(efficiency, 2),
            rank_score=round(rank_score, 4),
            action_type=entry.get("action_type", "investigate"),
            reasoning="",
            status="pending",
        )
        plays.append(play)

    # Sort descending by rank score
    plays.sort(key=lambda p: p.rank_score, reverse=True)

    for play in plays:
        db.add(play)
    db.commit()

    # Generate baseline and scenario forecasts for each play
    weekly = get_weekly_at_risk(db)
    for play in plays:
        baseline = forecast_baseline(weekly)
        scenario = forecast_scenario(baseline, play.expected_recovery, play.action_effectiveness)

        forecast = Forecast(
            id=generate_id(),
            play_id=play.id,
            horizon_days=28,
            baseline_projection=baseline,
            scenario_projection=scenario,
            effectiveness_rate_used=play.action_effectiveness,
        )
        db.add(forecast)

        if len(weekly) >= 6:
            play.forecast_confidence = 0.8
        elif len(weekly) >= 4:
            play.forecast_confidence = 0.6
        else:
            play.forecast_confidence = 0.4

    db.commit()
    return plays


def get_play_summary(plays: list) -> dict:
    if not plays:
        return {
            "plays_generated": 0,
            "total_revenue_at_risk": 0,
            "total_recoverable": 0,
            "total_expected_recovery": 0,
        }

    return {
        "plays_generated": len(plays),
        "total_revenue_at_risk": round(sum(p.affected_amount for p in plays), 2),
        "total_recoverable": round(sum(p.eligible_recovery for p in plays), 2),
        "total_expected_recovery": round(sum(p.expected_recovery for p in plays), 2),
    }
