# Main FastAPI backend application
# Exposes endpoints for pipeline execution, plays, copilot questions, and action triggers

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI, Depends, HTTPException, Request, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from pydantic import BaseModel
import datetime
import uuid
import io
import pandas as pd
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


# Dynamic Configuration Models & Endpoints
class LlmKeyRequest(BaseModel):
    provider: str = "gemini"
    api_key: str

class RazorpayConfigRequest(BaseModel):
    key_id: str
    key_secret: str
    webhook_secret: str = ""

@app.get("/api/config/status")
def get_config_status():
    gemini_key = os.getenv("GEMINI_API_KEY", "").strip()
    anthropic_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    has_llm = bool(gemini_key or anthropic_key)
    rzp_key = os.getenv("RAZORPAY_KEY_ID", "").strip()
    return {
        "has_llm_key": has_llm,
        "llm_provider": os.getenv("LLM_PROVIDER", "gemini"),
        "has_razorpay_keys": bool(rzp_key),
        "razorpay_key_id": (rzp_key[:6] + "...") if rzp_key else ""
    }

@app.post("/api/config/llm-key")
def set_llm_key(req: LlmKeyRequest):
    key = req.api_key.strip()
    provider = req.provider.lower()
    if provider == "claude":
        os.environ["ANTHROPIC_API_KEY"] = key
        os.environ["LLM_PROVIDER"] = "claude"
    else:
        os.environ["GEMINI_API_KEY"] = key
        os.environ["LLM_PROVIDER"] = "gemini"
    
    # Also write to backend/.env if exists
    try:
        env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
        if os.path.exists(env_path):
            with open(env_path, "r") as f:
                lines = f.readlines()
            new_lines = []
            target_var = "ANTHROPIC_API_KEY" if provider == "claude" else "GEMINI_API_KEY"
            found_target = False
            for line in lines:
                if line.startswith(f"{target_var}="):
                    new_lines.append(f"{target_var}={key}\n")
                    found_target = True
                elif line.startswith("LLM_PROVIDER="):
                    new_lines.append(f"LLM_PROVIDER={provider}\n")
                else:
                    new_lines.append(line)
            if not found_target:
                new_lines.append(f"{target_var}={key}\n")
            with open(env_path, "w") as f:
                f.writelines(new_lines)
    except Exception:
        pass
    return {"status": "success", "has_llm_key": True, "provider": provider}

@app.post("/api/config/razorpay")
def set_razorpay_config(req: RazorpayConfigRequest):
    os.environ["RAZORPAY_KEY_ID"] = req.key_id.strip()
    os.environ["RAZORPAY_KEY_SECRET"] = req.key_secret.strip()
    if req.webhook_secret:
        os.environ["RAZORPAY_WEBHOOK_SECRET"] = req.webhook_secret.strip()
    
    try:
        env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
        if os.path.exists(env_path):
            with open(env_path, "r") as f:
                lines = f.readlines()
            new_lines = []
            for line in lines:
                if line.startswith("RAZORPAY_KEY_ID="):
                    new_lines.append(f"RAZORPAY_KEY_ID={req.key_id.strip()}\n")
                elif line.startswith("RAZORPAY_KEY_SECRET="):
                    new_lines.append(f"RAZORPAY_KEY_SECRET={req.key_secret.strip()}\n")
                elif line.startswith("RAZORPAY_WEBHOOK_SECRET="):
                    new_lines.append(f"RAZORPAY_WEBHOOK_SECRET={req.webhook_secret.strip()}\n")
                else:
                    new_lines.append(line)
            with open(env_path, "w") as f:
                f.writelines(new_lines)
    except Exception:
        pass

    return {"status": "connected", "key_id": req.key_id[:6] + "..."}

@app.post("/api/seed")
def seed_and_run(db: Session = Depends(get_db)):
    from seed import seed_data
    seed_data()
    return run_full_pipeline(db)

@app.post("/api/upload-transactions")
async def upload_transactions(file: UploadFile = File(...), db: Session = Depends(get_db)):
    contents = await file.read()
    if file.filename.endswith(".xlsx") or file.filename.endswith(".xls"):
        df = pd.read_excel(io.BytesIO(contents))
    else:
        df = pd.read_csv(io.BytesIO(contents))
    
    now = datetime.datetime.now(datetime.UTC)
    count = 0
    for _, row in df.iterrows():
        pay_id = str(row.get("payment_id", f"pay_up_{uuid.uuid4().hex[:10]}"))
        order_id = str(row.get("order_id", f"order_up_{uuid.uuid4().hex[:10]}"))
        try:
            amount = float(row.get("amount", 1000))
        except (ValueError, TypeError):
            amount = 1000.0
        status = str(row.get("status", "failed")).lower()
        method = str(row.get("method", "upi")).lower()
        bank = str(row.get("bank", "HDFC"))
        error_reason = str(row.get("error_reason", "upi_timeout")) if status == "failed" else None
        error_source = str(row.get("error_source", "gateway")) if status == "failed" else None

        order = models.Order(
            id=order_id, amount=amount,
            amount_paid=amount if status == "captured" else 0,
            amount_due=0 if status == "captured" else amount,
            status="paid" if status == "captured" else "attempted",
            created_at=now
        )
        payment = models.Payment(
            id=pay_id, order_id=order_id, amount=amount,
            status=status, captured=(status == "captured"),
            method=method, bank=bank,
            error_source=error_source, error_step="payment_processing",
            error_reason=error_reason, created_at=now
        )
        db.add(order)
        db.add(payment)
        count += 1
    db.commit()
    pipeline_res = run_full_pipeline(db)
    return {
        "status": "success",
        "records_imported": count,
        "pipeline": pipeline_res
    }


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
