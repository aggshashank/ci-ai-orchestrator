"""
Explainability agent.
"""
import asyncio
import json
import time
from datetime import datetime, timezone

import structlog

from agents.state import GraphState
from llm.factory import get_llm
from rules.engine import get_rules_engine

logger = structlog.get_logger()

EXPLAIN_PROMPT = """\
You are a compliance officer writing an explanation for a credit card decision.

Decision: {recommendation}
Confidence: {confidence}

Signals:
- Credit risk: {credit_risk} - {credit_reason}
- Fraud risk: {fraud_risk} - {fraud_reason}
- Policy rules triggered: {policy_rules}

Write a clear, professional explanation. Return ONLY a JSON object:
{{
  "plain_language_summary": "1-2 sentence customer-facing explanation (no jargon)",
  "audit_narrative": "2-3 sentence internal compliance narrative with specific factors",
  "recommended_next_steps": "what the customer or underwriter should do next"
}}
"""


def _derive_adverse_codes(state: GraphState) -> list[dict]:
    app = state["application"]
    engine = get_rules_engine()

    # Evaluate all rule sets against this application's signals to collect ECOA codes.
    credit_matches = engine.evaluate_credit(
        app.creditScore, app.utilization, app.delinquencies or 0
    )
    fraud_matches = engine.evaluate_fraud(
        app.addressMismatch, app.delinquencies or 0, app.channel or "WEB"
    )

    seen: set[str] = set()
    codes: list[dict] = []
    for match in credit_matches + fraud_matches:
        for code in match.ecoa_codes:
            if code not in seen:
                seen.add(code)
                codes.append({"code": code, "description": match.rule_name.replace("_", " ")})

    if state.get("policy_context", {}).get("policy_applicable") and "AA12" not in seen:
        codes.append({"code": "AA12", "description": "Application does not meet policy criteria"})

    return codes


async def _persist_decision(audit_record: dict) -> None:
    try:
        from db.repository import DecisionRepository
        from db.session import get_session

        async with get_session() as session:
            repo = DecisionRepository(session)
            await repo.save_decision(audit_record)
    except Exception as exc:
        logger.error(
            "decision_persist failed - decision NOT stored in DB",
            error_type=type(exc).__name__,
            correlation_id=audit_record.get("correlation_id"),
        )


def explainability_agent(state: GraphState) -> dict:
    start = time.time()
    corr = state["correlation_id"]
    decision = state.get("risk_decision", {})

    logger.info(
        "explainability_agent start",
        correlation_id=corr,
        recommendation=decision.get("recommendation"),
    )

    credit = state.get("credit_result", {})
    fraud = state.get("fraud_result", {})
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
    except Exception as exc:
        logger.error(
            "explainability LLM failed",
            correlation_id=corr,
            error_type=type(exc).__name__,
        )
        llm_result = {
            "plain_language_summary": "Your application is under review.",
            "audit_narrative": "Explainability agent fallback applied after processing error.",
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
        "strategy_version": decision.get("strategy_version", get_rules_engine().strategy_version),
        "application": state["application"].model_dump(),
        "credit_result": credit,
        "fraud_result": fraud,
        "policy_context": policy,
        "risk_decision": decision,
        "explanation": explanation,
    }

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.ensure_future(_persist_decision(audit_record))
        else:
            loop.run_until_complete(_persist_decision(audit_record))
    except Exception as exc:
        logger.error(
            "explainability_agent persist dispatch failed",
            correlation_id=corr,
            error_type=type(exc).__name__,
        )

    latency = round(time.time() - start, 2)
    logger.info(
        "explainability_agent complete",
        correlation_id=corr,
        adverse_codes=[code["code"] for code in adverse_codes],
        latency_s=latency,
    )

    return {"explanation": explanation}
