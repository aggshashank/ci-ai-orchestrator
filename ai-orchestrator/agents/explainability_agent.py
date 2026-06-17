"""
Explainability agent (async).
"""
import asyncio
import json
import time
from datetime import datetime, timezone

import structlog

from agents.state import GraphState
from config import get_settings
from llm.factory import cached_llm_invoke
from prompts.registry import get_prompt_registry
from rules.engine import get_engine_for_state

logger = structlog.get_logger()


def _derive_adverse_codes(state: GraphState) -> list[dict]:
    app = state["application"]
    engine = get_engine_for_state(state)

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


async def explainability_agent(state: GraphState) -> dict:
    start = time.time()
    corr = state["correlation_id"]
    decision = state.get("risk_decision", {})

    logger.info(
        "explainability_agent start",
        correlation_id=corr,
        recommendation=decision.get("recommendation"),
    )

    credit = state.get("credit_result", {})
    fraud  = state.get("fraud_result", {})
    policy = state.get("policy_context", {})

    settings = get_settings()
    template = get_prompt_registry().get("explainability_agent", settings.explainability_agent_prompt_version)
    prompt = template.format(
        recommendation=decision.get("recommendation", "UNKNOWN"),
        confidence=decision.get("confidence", 0),
        credit_risk=credit.get("riskLevel", "UNKNOWN"),
        credit_reason=credit.get("reason", ""),
        fraud_risk=fraud.get("fraudRisk", "UNKNOWN"),
        fraud_reason=fraud.get("reason", ""),
        policy_rules="; ".join(policy.get("rules", []) or ["None triggered"]),
    )

    try:
        raw = await asyncio.to_thread(cached_llm_invoke, prompt)
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

    # ECOA adverse action codes only apply to origination decisions
    if state.get("decision_type", "ORIGINATION") == "ORIGINATION":
        adverse_codes = _derive_adverse_codes(state)
    else:
        adverse_codes = []

    explanation = {
        **llm_result,
        "adverse_action_codes": adverse_codes,
        "policy_citations": policy.get("rules", []),
        "signal_weights": decision.get("signal_weights", {}),
    }

    prompt_versions = {
        "credit_agent":          settings.credit_agent_prompt_version,
        "fraud_agent":           settings.fraud_agent_prompt_version,
        "policy_rag_agent":      settings.policy_rag_agent_prompt_version,
        "explainability_agent":  settings.explainability_agent_prompt_version,
        "limit_review_agent":    settings.limit_review_agent_prompt_version,
        "treatment_agent":       settings.treatment_agent_prompt_version,
        "propensity_agent":      settings.propensity_agent_prompt_version,
    }

    decision_type = state.get("decision_type", "ORIGINATION")
    app = state.get("application")

    audit_record = {
        "correlation_id":          corr,
        "timestamp":               datetime.now(timezone.utc).isoformat(),
        "decision_type":           decision_type,
        "recommendation":          decision.get("recommendation"),
        "confidence":              decision.get("confidence"),
        "composite_score":         decision.get("composite_score", 0.0),
        "strategy_version":        decision.get("strategy_version", get_engine_for_state(state).strategy_version),
        "experiment_variant":      state.get("experiment_variant", ""),
        "prompt_versions":         prompt_versions,
        "customer_id":             state.get("customer_id") or (getattr(app, "customerId", None) if app else None),
        "customer_context_version": state.get("customer_context_version"),
        "customer_profile":        state.get("customer_profile"),
        "application":             app.model_dump() if app else {},
        "credit_result":           credit,
        "fraud_result":            fraud,
        "policy_context":          policy,
        "risk_decision":           decision,
        "explanation":             explanation,
    }

    # Fully async now — no event loop gymnastics needed
    await _persist_decision(audit_record)

    latency = round(time.time() - start, 2)
    logger.info(
        "explainability_agent complete",
        correlation_id=corr,
        adverse_codes=[code["code"] for code in adverse_codes],
        latency_s=latency,
    )

    return {"explanation": explanation}
