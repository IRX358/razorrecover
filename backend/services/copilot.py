# Grounded LLM copilot service
# The LLM never calculates or invents numbers; it only reasons over pre-computed facts

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm import Session
from models import RecoveryPlay, Evidence, Forecast
from services.llm_service import ask_llm


SYSTEM_PROMPT = """You are the AI Recovery Copilot for a Razorpay merchant.

RULES YOU MUST FOLLOW:
1. You NEVER calculate, estimate, or invent any financial number. Every ₹ amount, 
   percentage, and score you mention must come EXACTLY from the data provided to you.
2. You explain WHY a recovery play is recommended, using the evidence provided.
3. You connect every answer to ₹ impact — not abstract metrics.
4. You clearly label statements as: FACT (from data), INFERENCE (from evidence pattern), 
   or ESTIMATE (from forecast projection).
5. You speak in ₹, not percentages or z-scores. Translate technical metrics into 
   business language the merchant can act on.
6. You are a recovery strategist, not an analytics narrator. Your job is to help 
   the merchant recover money, not understand charts.
7. If you don't have data to answer a question, say so. Never fabricate.
8. Keep responses concise and action-oriented. Under 200 words.

TONE: Direct, confident, business-focused. Like a CFO's advisor, not a data scientist."""


def generate_play_reasoning(play: RecoveryPlay, evidence: Evidence, forecast: Forecast) -> str:
    forecast_baseline = forecast.baseline_projection if forecast else []
    forecast_scenario = forecast.scenario_projection if forecast else []

    user_message = f"""Generate a clear, concise explanation for this Recovery Play.

PLAY DATA (pre-computed facts — cite them exactly):
- Segment: {play.segment_key}
- Leak category: {play.leak_category}
- Revenue at risk: ₹{play.affected_amount:,.0f}
- Eligible recovery: ₹{play.eligible_recovery:,.0f}
- Expected recovery: ₹{play.expected_recovery:,.0f}
- Recommended action: {play.action_type}
- Diagnosis confidence: {play.diagnosis_confidence * 100:.0f}%

EVIDENCE:
- Anomaly score: {evidence.anomaly_score if evidence else 'N/A'}σ above baseline
- Affected transactions: {evidence.affected_count if evidence else 'N/A'}
- Segment: {evidence.segment_key if evidence else 'N/A'}

FORECAST (4-week projection):
- Baseline (do nothing): {forecast_baseline}
- Scenario (with this play): {forecast_scenario}

Structure your response as:
CAUSE: [one sentence explaining the problem in business language]
EVIDENCE: [2-3 bullet points citing the data above]
RECOMMENDED ACTION: [what the merchant should do]
EXPECTED IMPACT: [₹ amount and timeframe, using the pre-computed numbers]"""

    return ask_llm(SYSTEM_PROMPT, user_message)


def answer_question(question: str, db: Session) -> str:
    plays = db.query(RecoveryPlay).order_by(RecoveryPlay.rank_score.desc()).all()

    if not plays:
        return "No recovery plays have been generated yet. Please run the analysis pipeline first."

    total_at_risk = sum(p.affected_amount for p in plays)
    total_recoverable = sum(p.eligible_recovery for p in plays)
    total_expected = sum(p.expected_recovery for p in plays)

    plays_summary = []
    for i, p in enumerate(plays[:5]):
        plays_summary.append(
            f"  #{i+1}: {p.segment_key} ({p.leak_category}) — "
            f"At risk: ₹{p.affected_amount:,.0f}, "
            f"Expected recovery: ₹{p.expected_recovery:,.0f}, "
            f"Action: {p.action_type}, "
            f"Confidence: {p.diagnosis_confidence * 100:.0f}%"
        )

    context_text = "\n".join(plays_summary)

    user_message = f"""The merchant asks: "{question}"

AVAILABLE DATA (use ONLY these numbers — do not invent any):
- Total revenue at risk: ₹{total_at_risk:,.0f}
- Total recoverable (eligible): ₹{total_recoverable:,.0f}
- Total expected recovery: ₹{total_expected:,.0f}
- Number of recovery plays: {len(plays)}
- Top recovery plays:
{context_text}

Answer the question using ONLY the data above.
Connect your answer to ₹ impact.
If the question requires data you don't have, say so honestly."""

    return ask_llm(SYSTEM_PROMPT, user_message)


def generate_all_reasoning(db: Session) -> int:
    plays = db.query(RecoveryPlay).order_by(RecoveryPlay.rank_score.desc()).all()
    count = 0

    for play in plays:
        evidence = db.query(Evidence).filter(
            Evidence.segment_key == play.segment_key
        ).first()
        forecast = db.query(Forecast).filter(
            Forecast.play_id == play.id
        ).first()

        reasoning = generate_play_reasoning(play, evidence, forecast)
        play.reasoning = reasoning
        count += 1

    db.commit()
    return count
