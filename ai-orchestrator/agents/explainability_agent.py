"""
Explainability Agent
--------------------
Generates audit-friendly, ECOA-compliant explanations.
Persists the full decision record to PostgreSQL via DecisionRepository.
"""
import asyncio
import json
import time
import structlog
from datetime import datetime, timezone
from agents.state import GraphState
from llm.factory import get_llm

logger = structlog.get_logger()

# ECOA-style adverse action codes
ADVERSE_ACTION_CODES = {
    "low_credit_score":  ("AA01", "Credit score below minimum threshold"),
    "high_utilization":  ("AA04", "Revolving credit utilization too high"),
    "address_mismatch":  ("AA07", "Address verification failed"),
    "delinquencies":     ("AA09", "Recent delinquencies on credit report"),
    "policy_threshold":  ("AA12", "Application does not meet policy criteria"),
}

EXPLAIN_PROMPT = """\
You are a compliance officer writing an explanation for a credit card decision.

Decision: {recommendation}
Confidence: {confidence}

Signals:
- Credit risk: {credit_risk} — {credit_reason}
- Fraud risk: {fraud_risk} — {fraud_reason}
- Policy rules triggered: {policy_rules}

Write a clear, professional explanation. Return ONLY a JSON object:
{{
  "plain_language_summary": "1-2 sentence customer-facing explanation (no jargon)",
  "audit_narrative": "2-3 sentence internal compliance narrative with specific factors",
  "recommended_next_steps": "what the customer or underwriter should do next"
}}
"""


def _derive_adverse_codes(state: GraphState) -> list[dict]:
    codes = []
    app = state["application"]
    if app.creditScore < 580:
        codes.append(ADVERSE_ACTION_CODES["low_credit_score"])
    if app.utilization > 80:
        codes.append(ADVERSE_ACTION_CODES["high_utilization"])
    if app.addressMismatch:
        codes.append(ADVERSE_ACTION_CODES["address_mismatch"])
    if (app.delinquencies or 0) > 0:
        codes.append(ADVERSE_ACTION_CODES["delinquencies"])
    if state.get("policy_context", {}).get("policy_applicable"):
        codes.append(ADVERSE_ACTION_CODES["policy_threshold"])
    return [{"code": c[0], "description": c[1]} for c in codes]


async def _persist_decision(audit_record: dict) -> None:
    """Write the full audit record to PostgreSQL (best-effort; never raises)."""
    try:
        from db.session import get_session
        from db.repository import DecisionRepository
        async with get_session() as session:
            repo = DecisionRepository(session)
            await repo.save_decision(audit_record)
    except Exception as e:
        logger.error("decision_persist failed — decision NOT stored in DB",
                     error=str(e), correlation_id=audit_record.get("correlation_id"))


def explainability_agent(state: GraphState) -> dict:
    start = time.time()
    corr = state["correlation_id"]
    decision = state.get("risk_decision", {})

    logger.info("explainability_agent start", correlation_id=corr,
                recommendation=decision.get("recommendation"))

    credit = state.get("credit_result", {})
    fraud  = state.get("fraud_result", {})
    policy = state.get("policy_context", {})

    prompt = EXPLAIN_PROMPT.format(
        recommendation=decision.get("recommendation", "UNKNOWN"),
        confidence=decision.get("confidence", 0),
        credit_risk=credit.get("riskLevel", "UNKNOWN"),
        credit_reason=credit.get("reason", ""),
        fraud_risk=fraud.get("fraudRisk", "UNKNOWN"),
        fraud_reason=fraud.get("reason", ""),
        policy_rules="; ".join(policy.get("rules", []) or ["None triggered"]),
    )

    try:
        llm = get_llm()
        raw = llm.invoke(prompt)
        llm_result = json.loads(raw)
    except Exception as e:
        logger.error("explainability LLM failed", error=str(e))
        llm_result = {
            "plain_language_summary": "Your application is under review.",
            "audit_narrative": f"Explainability agent encountered an error: {str(e)}",
            "recommended_next_steps": "Contact customer service.",
        }

    adverse_codes = _derive_adverse_codes(state)

    explanation = {
        **llm_result,
        "adverse_action_codes": adverse_codes,
        "policy_citations": policy.get("rules", []),
        "signal_weights": decision.get("signal_weights", {}),
    }

    audit_record = {
        "correlation_id": corr,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "recommendation": decision.get("recommendation"),
        "confidence": decision.get("confidence"),
        "composite_score": decision.get("composite_score", 0.0),
        "application": state["application"].model_dump(),
        "credit_result": credit,
        "fraud_result": fraud,
        "policy_context": policy,
        "risk_decision": decision,
        "explanation": explanation,
    }

    # Persist to PostgreSQL — run async persist in the current event loop if available,
    # otherwise create one (handles both FastAPI and Kafka consumer call paths).
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.ensure_future(_persist_decision(audit_record))
        else:
            loop.run_until_complete(_persist_decision(audit_record))
    except Exception as e:
        logger.error("explainability_agent persist dispatch failed", error=str(e))

    latency = round(time.time() - start, 2)
    logger.info("explainability_agent complete", correlation_id=corr,
                adverse_codes=[c["code"] for c in adverse_codes],
                latency_s=latency)

    return {"explanation": explanation}
