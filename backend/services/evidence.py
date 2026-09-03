# Anomaly detection via rolling z-scores
# Finds outlier segments (bank x method or leak category) with statistically abnormal failures

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
from sqlalchemy.orm import Session
from models import RevenueClassification, Payment, Evidence, generate_id


def detect_anomalies(db: Session, z_threshold: float = 2.0) -> list:
    query = """
        SELECT rc.payment_id, rc.transaction_state, rc.recovery_status,
               rc.leak_category, rc.amount AS rc_amount,
               p.method, p.bank, p.created_at, p.amount
        FROM revenue_classification rc
        JOIN payments p ON rc.payment_id = p.id
    """
    df = pd.read_sql(query, db.bind)

    if df.empty:
        return []

    df["bank"] = df["bank"].fillna("unknown")
    df["method"] = df["method"].fillna("unknown")
    df["is_eligible"] = (df["recovery_status"] == "ELIGIBLE").astype(int)

    results = []
    # 1. Look for anomalies by bank and method combination (e.g. HDFC upi)
    results.extend(_analyze_dimension(df, ["bank", "method"], z_threshold))

    # 2. Look for method-wide issues (e.g. all card payments dropping)
    results.extend(_analyze_dimension(df, ["method"], z_threshold))

    # 3. Check concentration by leak category
    eligible_df = df[df["is_eligible"] == 1].copy()
    if not eligible_df.empty and eligible_df["leak_category"].notna().any():
        leak_groups = eligible_df.groupby("leak_category").agg(
            affected_count=("payment_id", "count"),
            affected_amount=("rc_amount", "sum"),
        ).reset_index()

        for _, row in leak_groups.iterrows():
            if row["affected_count"] >= 3:
                results.append({
                    "segment_key": str(row["leak_category"]),
                    "metric": "leak_concentration",
                    "anomaly_score": round(row["affected_count"] / max(len(eligible_df), 1) * 5, 2),
                    "confidence": min(row["affected_count"] / 20.0, 1.0),
                    "affected_amount": round(row["affected_amount"], 2),
                    "affected_count": int(row["affected_count"]),
                    "leak_category": str(row["leak_category"]),
                })

    # Deduplicate: if segment appears multiple times, pick highest anomaly score
    seen = {}
    for r in results:
        key = r["segment_key"]
        if key not in seen or r["anomaly_score"] > seen[key]["anomaly_score"]:
            seen[key] = r
    results = list(seen.values())

    # Refresh evidence table with new findings
    db.query(Evidence).delete()
    for r in results:
        ev = Evidence(
            id=generate_id(),
            segment_key=r["segment_key"],
            metric=r["metric"],
            anomaly_score=r["anomaly_score"],
            confidence=r["confidence"],
            affected_amount=r["affected_amount"],
            affected_count=r["affected_count"],
        )
        db.add(ev)
    db.commit()

    return results


def _analyze_dimension(df: pd.DataFrame, group_cols: list, z_threshold: float) -> list:
    segment = df.groupby(group_cols).agg(
        total_count=("payment_id", "count"),
        eligible_count=("is_eligible", "sum"),
        affected_amount=("rc_amount", lambda x: df.loc[x.index][df.loc[x.index, "is_eligible"] == 1]["rc_amount"].sum()),
    ).reset_index()

    if segment.empty or len(segment) < 2:
        return []

    segment["failure_rate"] = segment["eligible_count"] / segment["total_count"]
    mean_rate = segment["failure_rate"].mean()
    std_rate = segment["failure_rate"].std()

    if std_rate == 0 or pd.isna(std_rate):
        return []

    segment["z_score"] = (segment["failure_rate"] - mean_rate) / std_rate

    anomalies = segment[segment["z_score"].abs() > z_threshold]

    results = []
    for _, row in anomalies.iterrows():
        seg_key = "_".join(str(row[c]) for c in group_cols)
        leak_cat = None
        if "method" in group_cols:
            method = row.get("method", "")
            if method == "upi":
                leak_cat = "upi_timeout"
            elif method == "card":
                leak_cat = "card_decline"
            elif method == "netbanking":
                leak_cat = "gateway_error"

        results.append({
            "segment_key": seg_key,
            "metric": "failure_rate",
            "anomaly_score": round(float(row["z_score"]), 2),
            "confidence": min(abs(float(row["z_score"])) / 4.0, 1.0),
            "affected_amount": round(float(row["affected_amount"]), 2),
            "affected_count": int(row["eligible_count"]),
            "leak_category": leak_cat,
        })

    return results
