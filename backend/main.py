# Main FastAPI backend application
# Exposes endpoints for pipeline execution, plays, copilot questions, and action triggers

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from pydantic import BaseModel
from database import engine, get_db
import models

from services.classification import classify_all, get_summary
from services.evidence import detect_anomalies
from services.scoring import score_all_evidence
from services.ranking import rank_and_create_plays, get_play_summary
from services.copilot import answer_question, generate_all_reasoning
from services.action import check_eligibility, execute_play
from services.forecasting import generate_forecast

models.Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="RazorRecover - AI Revenue Recovery Co-Pilot",
    description="Detect revenue leaks, quantify recoverable revenue, rank plays, execute bounded actions.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class QuestionRequest(BaseModel):
    question: str


@app.get("/api/health")
def health_check():
    return {"status": "ok", "service": "RazorRecover"}


# Core summary for dashboard cards
@app.get("/api/summary")
def get_dashboard_summary(db: Session = Depends(get_db)):
    summary = get_summary(db)
    if summary["total_payments"] == 0:
        return {**summary, "message": "No classifications yet. Run /api/run-pipeline first."}
    return summary


@app.post("/api/classify")
def run_classification(db: Session = Depends(get_db)):
    results = classify_all(db)
    summary = get_summary(db)
    return {
        "classified": len(results),
        "summary": summary,
    }


# Anomaly evidence records
@app.get("/api/evidence")
def get_evidence(db: Session = Depends(get_db)):
    evidence = db.query(models.Evidence).order_by(models.Evidence.anomaly_score.desc()).all()
    return [
        {
            "id": e.id,
            "segment_key": e.segment_key,
            "metric": e.metric,
            "anomaly_score": e.anomaly_score,
            "confidence": e.confidence,
            "affected_amount": e.affected_amount,
            "affected_count": e.affected_count,
        }
        for e in evidence
    ]


# Ranked recovery plays
@app.get("/api/plays")
def get_plays(db: Session = Depends(get_db)):
    plays = db.query(models.RecoveryPlay).order_by(
        models.RecoveryPlay.rank_score.desc()
    ).all()
    return [_play_to_dict(p, i + 1) for i, p in enumerate(plays)]


@app.get("/api/plays/{play_id}")
def get_play_detail(play_id: str, db: Session = Depends(get_db)):
    play = db.query(models.RecoveryPlay).filter(models.RecoveryPlay.id == play_id).first()
    if not play:
        raise HTTPException(status_code=404, detail="Play not found")

    forecast = db.query(models.Forecast).filter(models.Forecast.play_id == play_id).first()
    evidence = db.query(models.Evidence).filter(
        models.Evidence.segment_key == play.segment_key
    ).first()

    result = _play_to_dict(play, 0)
    result["forecast"] = {
        "baseline": forecast.baseline_projection if forecast else [],
        "scenario": forecast.scenario_projection if forecast else [],
        "horizon_days": forecast.horizon_days if forecast else 28,
    } if forecast else None
    result["evidence_detail"] = {
        "anomaly_score": evidence.anomaly_score,
        "confidence": evidence.confidence,
        "affected_count": evidence.affected_count,
    } if evidence else None

    return result


# Full loop execution: Classify -> Detect -> Score -> Rank -> Forecast
@app.post("/api/run-pipeline")
def run_full_pipeline(db: Session = Depends(get_db)):
    classifications = classify_all(db)
    anomalies = detect_anomalies(db)
    scored = score_all_evidence(anomalies, db)
    plays = rank_and_create_plays(scored, db)

    summary = get_summary(db)
    play_summary = get_play_summary(plays)

    return {
        "pipeline": "complete",
        "classifications": len(classifications),
        "anomalies_detected": len(anomalies),
        "plays_generated": play_summary["plays_generated"],
        "summary": summary,
        "play_summary": play_summary,
        "top_plays": [
            {
                "rank": i + 1,
                "segment": p.segment_key,
                "leak": p.leak_category,
                "action": p.action_type,
                "expected_recovery": p.expected_recovery,
                "confidence": p.diagnosis_confidence,
            }
            for i, p in enumerate(plays[:5])
        ],
    }


# Grounded LLM copilot question answering
@app.post("/api/copilot/ask")
def ask_copilot(request: QuestionRequest, db: Session = Depends(get_db)):
    answer = answer_question(request.question, db)
    return {"question": request.question, "answer": answer}


@app.post("/api/copilot/generate-reasoning")
def generate_reasoning(db: Session = Depends(get_db)):
    count = generate_all_reasoning(db)
    return {"status": "reasoning generated", "plays_updated": count}


# Gated action execution with idempotency
@app.post("/api/plays/{play_id}/check-eligibility")
def check_play_eligibility(play_id: str, db: Session = Depends(get_db)):
    play = db.query(models.RecoveryPlay).filter(models.RecoveryPlay.id == play_id).first()
    if not play:
        raise HTTPException(status_code=404, detail="Play not found")
    return check_eligibility(play, db)


@app.post("/api/plays/{play_id}/execute")
def execute_recovery_play(play_id: str, db: Session = Depends(get_db)):
    play = db.query(models.RecoveryPlay).filter(models.RecoveryPlay.id == play_id).first()
    if not play:
        raise HTTPException(status_code=404, detail="Play not found")

    eligibility = check_eligibility(play, db)
    if not eligibility["eligible"]:
        raise HTTPException(status_code=400, detail=eligibility["reason"])

    return execute_play(play, db)


# Audit trail
@app.get("/api/audit-log")
def get_audit_log(db: Session = Depends(get_db)):
    logs = db.query(models.AuditLog).order_by(models.AuditLog.timestamp.desc()).all()
    return [
        {
            "id": log.id,
            "actor": log.actor,
            "action_id": log.action_id,
            "timestamp": log.timestamp.isoformat() if log.timestamp else None,
            "details": log.details_json,
        }
        for log in logs
    ]


# Transparent benchmark assumptions table
@app.get("/api/assumptions")
def get_assumptions(db: Session = Depends(get_db)):
    assumptions = db.query(models.Assumption).all()
    return [
        {
            "id": a.id,
            "cause_type": a.cause_type,
            "recoverable_fraction": a.recoverable_fraction,
            "action_effectiveness": a.action_effectiveness,
            "estimated_effort": a.estimated_effort,
            "source_note": a.source_note,
            "editable": a.editable,
        }
        for a in assumptions
    ]


# Webhook endpoint for live Razorpay events
@app.post("/webhook")
async def razorpay_webhook(request: Request, db: Session = Depends(get_db)):
    payload = await request.json()
    event = payload.get("event", "")

    log = models.AuditLog(
        actor="razorpay_webhook",
        details_json={"event": event, "payload_keys": list(payload.keys())},
    )
    db.add(log)
    db.commit()

    return {"status": "received", "event": event}


def _play_to_dict(play: models.RecoveryPlay, rank: int) -> dict:
    return {
        "id": play.id,
        "rank": rank,
        "leak_category": play.leak_category,
        "segment_key": play.segment_key,
        "affected_amount": play.affected_amount,
        "recoverable_fraction": play.recoverable_fraction,
        "eligible_recovery": play.eligible_recovery,
        "action_effectiveness": play.action_effectiveness,
        "expected_recovery": play.expected_recovery,
        "diagnosis_confidence": play.diagnosis_confidence,
        "forecast_confidence": play.forecast_confidence,
        "recovery_efficiency_score": play.recovery_efficiency_score,
        "rank_score": play.rank_score,
        "action_type": play.action_type,
        "reasoning": play.reasoning,
        "status": play.status,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
