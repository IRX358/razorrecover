# End-to-end evaluation harness
# Validates the full pipeline against known ground truth data (~Rs.198k)

import sys
import os
import json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import engine, SessionLocal
import models
from services.classification import classify_all, get_summary
from services.evidence import detect_anomalies
from services.scoring import score_all_evidence
from services.ranking import rank_and_create_plays
from services.action import check_eligibility, execute_play

models.Base.metadata.create_all(bind=engine)

# Ground truth recoverable target from scenario seed design
GROUND_TRUTH_RECOVERABLE = 198000


def run_batch_evaluation():
    db = SessionLocal()

    print("=" * 60)
    print("  BATCH EVALUATION REPORT")
    print("  RazorRecover Pipeline")
    print("=" * 60)
    print()

    # 1. 2D Classification
    print("[1/5] Classifying transactions...")
    classifications = classify_all(db)
    summary = get_summary(db)
    print(f"      Total classified: {len(classifications)}")
    print(f"      Revenue at risk: Rs. {summary['revenue_at_risk']:,.0f}")
    print(f"      Recoverable: Rs. {summary['recoverable_revenue']:,.0f}")
    print()

    # 2. Z-Score Anomaly Detection
    print("[2/5] Scanning for anomaly evidence...")
    anomalies = detect_anomalies(db)
    print(f"      Clusters found: {len(anomalies)}")
    for a in anomalies:
        print(f"        - {a['segment_key']}: z={a['anomaly_score']}, affected=Rs. {a['affected_amount']:,.0f}")
    print()

    # 3. Yield Scoring
    print("[3/5] Scoring recovery yield...")
    scored = score_all_evidence(anomalies, db)
    print(f"      Scored clusters: {len(scored)}")
    print()

    # 4. Opportunity Ranking & Forecasting
    print("[4/5] Ranking recovery plays...")
    plays = rank_and_create_plays(scored, db)
    print(f"      Plays created: {len(plays)}")
    for i, p in enumerate(plays):
        print(f"        #{i+1}: {p.segment_key} ({p.leak_category})")
        print(f"            Affected: Rs. {p.affected_amount:,.0f}")
        print(f"            Eligible: Rs. {p.eligible_recovery:,.0f}")
        print(f"            Expected: Rs. {p.expected_recovery:,.0f}")
        print(f"            Confidence: {p.diagnosis_confidence * 100:.0f}%")
        print(f"            Rank Score: {p.rank_score}")
    print()

    # 5. Simulated Gated Execution
    print("[5/5] Testing execution gateway...")
    results = []
    exceptions = []
    for play in plays:
        eligibility = check_eligibility(play, db)
        if eligibility["eligible"]:
            result = execute_play(play, db)
            results.append(result)
            print(f"      {play.segment_key}: {result['status']} -> recovered Rs. {result['actual_recovered']:,.0f}")
            if result["status"] not in ("verified",):
                exceptions.append({
                    "play_id": play.id,
                    "segment": play.segment_key,
                    "status": result["status"],
                    "reason": result.get("stopping_reason", "partial_recovery"),
                })
        else:
            print(f"      {play.segment_key}: SKIPPED ({eligibility['reason']})")
            exceptions.append({
                "play_id": play.id,
                "segment": play.segment_key,
                "status": "skipped",
                "reason": eligibility["reason"],
            })
    print()

    total_at_risk = sum(p.affected_amount for p in plays)
    total_recoverable = sum(p.eligible_recovery for p in plays)
    total_expected = sum(p.expected_recovery for p in plays)
    total_recovered = sum(r["actual_recovered"] for r in results)

    precision = (total_recoverable / GROUND_TRUTH_RECOVERABLE * 100) if GROUND_TRUTH_RECOVERABLE > 0 else 0
    recovery_rate = (total_recovered / total_recoverable * 100) if total_recoverable > 0 else 0

    forecast_errors = []
    for play, result in zip(plays, results):
        if play.expected_recovery > 0:
            error = abs(play.expected_recovery - result["actual_recovered"])
            forecast_errors.append(error)

    avg_forecast_error = sum(forecast_errors) / len(forecast_errors) if forecast_errors else 0

    print("=" * 60)
    print("  FINAL ACCURACY & PERFORMANCE")
    print("=" * 60)
    print(f"  Ground Truth (injected):       Rs. {GROUND_TRUTH_RECOVERABLE:>10,.0f}")
    print(f"  System Identified:             Rs. {total_recoverable:>10,.0f}")
    print(f"  Identification Precision:      {precision:>9.1f}%")
    print()
    print(f"  Expected Recovery:             Rs. {total_expected:>10,.0f}")
    print(f"  Actually Recovered:            Rs. {total_recovered:>10,.0f}")
    print(f"  Realized Recovery Rate:        {recovery_rate:>9.1f}%")
    print()
    print(f"  Avg Forecast Error:            Rs. {avg_forecast_error:>10,.0f}")
    print(f"  Exception Count:               {len(exceptions):>9d}")
    print("=" * 60)

    report = {
        "ground_truth": GROUND_TRUTH_RECOVERABLE,
        "identified": round(total_recoverable, 2),
        "expected": round(total_expected, 2),
        "recovered": round(total_recovered, 2),
        "precision": round(precision, 2),
        "recovery_rate": round(recovery_rate, 2),
        "avg_forecast_error": round(avg_forecast_error, 2),
        "plays_count": len(plays),
        "exceptions": exceptions,
        "plays": [
            {
                "rank": i + 1,
                "segment": p.segment_key,
                "leak": p.leak_category,
                "affected": p.affected_amount,
                "eligible": p.eligible_recovery,
                "expected": p.expected_recovery,
                "confidence": p.diagnosis_confidence,
                "rank_score": p.rank_score,
            }
            for i, p in enumerate(plays)
        ],
    }

    output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "batch_eval_results.json")
    with open(output_path, "w") as f:
        json.dump(report, f, indent=2)

    print(f"\nReport written to: {output_path}")

    db.close()
    return report


if __name__ == "__main__":
    run_batch_evaluation()
