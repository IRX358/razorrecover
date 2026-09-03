# Time-series forecasting using Holt-Winters exponential smoothing
# Projects a baseline (do nothing) vs scenario (with recovery play) curve

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import numpy as np
from sqlalchemy.orm import Session


def get_weekly_at_risk(db: Session) -> list:
    query = """
        SELECT strftime('%Y-%W', p.created_at) as week,
               SUM(rc.amount) as total_at_risk
        FROM revenue_classification rc
        JOIN payments p ON rc.payment_id = p.id
        WHERE rc.recovery_status = 'ELIGIBLE'
        GROUP BY week
        ORDER BY week
    """
    try:
        result = pd.read_sql(query, db.bind)
        if result.empty:
            return []
        return result["total_at_risk"].tolist()
    except Exception:
        return []


def forecast_baseline(weekly_at_risk: list, horizon_weeks: int = 4) -> list:
    if not weekly_at_risk or len(weekly_at_risk) == 0:
        return [0.0] * horizon_weeks

    # fallback for small datasets with <4 data points
    if len(weekly_at_risk) < 4:
        avg = sum(weekly_at_risk) / len(weekly_at_risk)
        trend = (weekly_at_risk[-1] - weekly_at_risk[0]) / len(weekly_at_risk) if len(weekly_at_risk) >= 2 else 0
        return [max(0, round(avg + trend * (i + 1), 2)) for i in range(horizon_weeks)]

    try:
        from statsmodels.tsa.holtwinters import ExponentialSmoothing

        series = pd.Series(weekly_at_risk, dtype=float)
        model = ExponentialSmoothing(
            series,
            trend="add",
            seasonal=None,
            initialization_method="estimated"
        ).fit(optimized=True)

        projection = model.forecast(horizon_weeks)
        return [max(0, round(float(v), 2)) for v in projection.tolist()]

    except Exception:
        # linear extrapolation fallback if statsmodels fails
        avg = sum(weekly_at_risk) / len(weekly_at_risk)
        trend = (weekly_at_risk[-1] - weekly_at_risk[0]) / max(len(weekly_at_risk) - 1, 1)
        return [max(0, round(avg + trend * (i + 1), 2)) for i in range(horizon_weeks)]


def forecast_scenario(
    baseline: list,
    expected_recovery: float,
    effectiveness_rate: float,
    horizon_weeks: int = 4
) -> list:
    if not baseline:
        return [0.0] * horizon_weeks

    weekly_reduction = (expected_recovery * effectiveness_rate) / max(horizon_weeks, 1)
    scenario = [max(0, round(b - weekly_reduction, 2)) for b in baseline]
    return scenario


def generate_forecast(db: Session, expected_recovery: float, effectiveness: float) -> dict:
    weekly = get_weekly_at_risk(db)
    baseline = forecast_baseline(weekly)
    scenario = forecast_scenario(baseline, expected_recovery, effectiveness)

    return {
        "weekly_history": weekly,
        "baseline_projection": baseline,
        "scenario_projection": scenario,
        "horizon_weeks": 4,
    }
