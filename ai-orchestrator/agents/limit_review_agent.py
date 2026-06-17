"""
Limit Review Agent (async) — analyses utilization trend and payment behaviour.
"""
from __future__ import annotations

import asyncio
import json
import time

import structlog

from agents.state import GraphState
from config import get_settings
from llm.factory import cached_llm_invoke
from prompts.registry import get_prompt_registry
from rules.engine import get_engine_for_state

logger = structlog.get_logger()


async def limit_review_agent(state: GraphState) -> dict:
    start = time.time()
    corr = state["correlation_id"]
    req: dict = state.get("limit_review_request", {})
    profile: dict = state.get("customer_profile", {})

    logger.info("limit_review_agent start", correlation_id=corr,
                customer_id=req.get("customerId"))

    settings = get_settings()
    template = get_prompt_registry().get("limit_review_agent", settings.limit_review_agent_prompt_version)

    payments_on_time = req.get("paymentsMadeOnTime", 0)
    payments_total   = max(req.get("paymentsCounted", 12), 1)
    payment_rate     = round(payments_on_time / payments_total * 100, 1)
    current_limit    = req.get("currentCreditLimit", 0)
    utilization_avg  = req.get("recentUtilizationAvg", 0)

    prior_apps    = profile.get("prior_applications", [])
    prior_outcomes = ", ".join(
        f"{p.get('recommendation', '?')} ({p.get('decision_type', 'ORIGINATION')})"
        for p in prior_apps[:5]
    ) or "No prior history"
    util_trend = profile.get("utilization_trend_3m", [])

    prompt = template.format(
        customer_id=req.get("customerId", "unknown"),
        current_limit=current_limit,
        account_age_months=req.get("accountAgeMonths", 0),
        utilization_avg=utilization_avg,
        payment_rate=payment_rate,
        payments_on_time=payments_on_time,
        payments_total=payments_total,
        missed_payments=req.get("missedPayments", 0),
        current_balance=req.get("currentBalance", 0),
        consistency_score=profile.get("payment_consistency_score", 0.5),
        util_trend=util_trend or "unavailable",
        prior_outcomes=prior_outcomes,
        estimated_clv=profile.get("estimated_clv", 0),
    )

    try:
        raw = await asyncio.to_thread(cached_llm_invoke, prompt)
        result = json.loads(raw)

        required = {"recommendation", "suggested_change_pct", "suggested_new_limit", "confidence", "reasons"}
        if not required.issubset(result.keys()):
            raise ValueError(f"Missing fields: {required - result.keys()}")

        if not result.get("suggested_new_limit") and result.get("suggested_change_pct") is not None:
            change_pct = result["suggested_change_pct"]
            result["suggested_new_limit"] = round(current_limit * (1 + change_pct / 100), 2)

        engine = get_engine_for_state(state)
        latency = round(time.time() - start, 2)
        logger.info("limit_review_agent complete", correlation_id=corr,
                    recommendation=result["recommendation"], latency_s=latency)

        rec_map = {"INCREASE": "APPROVE", "MAINTAIN": "MANUAL_REVIEW", "DECREASE": "DECLINE"}

        return {
            "limit_review_result": result,
            "risk_decision": {
                "recommendation":    rec_map.get(result["recommendation"], "MANUAL_REVIEW"),
                "confidence":        result["confidence"],
                "composite_score":   result["confidence"],
                "reasons":           result.get("reasons", []),
                "strategy_version":  engine.strategy_version,
                "signal_weights":    {},
                "limit_recommendation":  result["recommendation"],
                "suggested_new_limit":   result.get("suggested_new_limit"),
            },
        }

    except Exception as exc:
        logger.error("limit_review_agent failed - fallback", correlation_id=corr,
                     error_type=type(exc).__name__)
        return {
            "limit_review_result": {
                "recommendation": "MAINTAIN",
                "suggested_change_pct": 0,
                "suggested_new_limit": current_limit,
                "confidence": 0.5,
                "reasons": ["Fallback applied after agent error"],
                "risk_factors": ["agent_error_fallback"],
            },
            "risk_decision": {
                "recommendation": "MANUAL_REVIEW",
                "confidence": 0.5,
                "composite_score": 0.5,
                "reasons": ["Limit review agent fallback"],
                "strategy_version": "unknown",
                "signal_weights": {},
            },
        }
