"""
Propensity Agent (async) — scores cross-sell product propensity.
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

logger = structlog.get_logger()


async def propensity_agent(state: GraphState) -> dict:
    start = time.time()
    corr = state["correlation_id"]
    req: dict = state.get("cross_sell_request", {})
    profile: dict = state.get("customer_profile", {})

    logger.info("propensity_agent start", correlation_id=corr,
                customer_id=req.get("customerId"),
                trigger=req.get("triggerReason"))

    settings = get_settings()
    template = get_prompt_registry().get("propensity_agent", settings.propensity_agent_prompt_version)

    prior_apps     = profile.get("prior_applications", [])
    prior_outcomes = ", ".join(p.get("recommendation", "?") for p in prior_apps[:5]) or "No prior history"

    prompt = template.format(
        customer_id=req.get("customerId", "unknown"),
        months_on_book=req.get("monthsOnBook", 0),
        current_product=req.get("currentProduct", "UNKNOWN"),
        avg_monthly_balance=req.get("averageMonthlyBalance", 0),
        annual_spend=req.get("annualSpend", 0),
        reward_points=req.get("rewardPointsBalance", 0),
        trigger_reason=req.get("triggerReason", "UNKNOWN"),
        consistency_score=profile.get("payment_consistency_score", 0.5),
        estimated_clv=profile.get("estimated_clv", 0),
        prior_outcomes=prior_outcomes,
    )

    try:
        raw = await asyncio.to_thread(cached_llm_invoke, prompt)
        result = json.loads(raw)

        required = {"recommended_product", "propensity_score", "eligible_products", "key_signals"}
        if not required.issubset(result.keys()):
            raise ValueError(f"Missing fields: {required - result.keys()}")

        latency = round(time.time() - start, 2)
        logger.info("propensity_agent complete", correlation_id=corr,
                    product=result["recommended_product"],
                    score=result["propensity_score"],
                    latency_s=latency)

        score = float(result.get("propensity_score", 0))
        if result["recommended_product"] == "NONE" or score < 0.4:
            recommendation = "DECLINE"
        elif score >= 0.7:
            recommendation = "APPROVE"
        else:
            recommendation = "MANUAL_REVIEW"

        return {
            "propensity_result": result,
            "risk_decision": {
                "recommendation":     recommendation,
                "confidence":         round(score, 3),
                "composite_score":    round(score, 3),
                "reasons":            result.get("key_signals", []),
                "strategy_version":   "propensity_v1",
                "signal_weights":     {},
                "recommended_product":  result["recommended_product"],
                "recommended_channel":  result.get("recommended_channel", "EMAIL"),
            },
        }

    except Exception as exc:
        logger.error("propensity_agent failed - fallback", correlation_id=corr,
                     error_type=type(exc).__name__)
        return {
            "propensity_result": {
                "recommended_product": "NONE",
                "propensity_score": 0.0,
                "eligible_products": [],
                "key_signals": ["agent_error_fallback"],
                "recommended_channel": "EMAIL",
            },
            "risk_decision": {
                "recommendation":  "DECLINE",
                "confidence":      0.0,
                "composite_score": 0.0,
                "reasons":         ["Propensity agent fallback"],
                "strategy_version": "unknown",
                "signal_weights":  {},
            },
        }
