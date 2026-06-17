"""
Treatment Agent (async) — selects collections treatment for a delinquent account.

DPD floor rule: the rules engine determines the minimum treatment; the LLM
may escalate above it but cannot de-escalate below it.
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

_DPD_FLOOR = {
    (0, 14):   "REMINDER",
    (15, 59):  "HARDSHIP_PROGRAM",
    (60, 999): "COLLECTIONS_REFERRAL",
}


def _dpd_floor(days_past_due: int) -> str:
    for (low, high), treatment in _DPD_FLOOR.items():
        if low <= days_past_due <= high:
            return treatment
    return "COLLECTIONS_REFERRAL"


async def treatment_agent(state: GraphState) -> dict:
    start = time.time()
    corr = state["correlation_id"]
    req: dict = state.get("delinquency_request", {})
    profile: dict = state.get("customer_profile", {})

    logger.info("treatment_agent start", correlation_id=corr,
                customer_id=req.get("customerId"),
                days_past_due=req.get("daysPastDue"))

    settings = get_settings()
    template = get_prompt_registry().get("treatment_agent", settings.treatment_agent_prompt_version)

    days_past_due   = req.get("daysPastDue", 0)
    current_limit   = req.get("currentCreditLimit", 1)
    current_balance = req.get("currentBalance", 0)
    utilization     = round(current_balance / max(current_limit, 1) * 100, 1)

    prior_apps     = profile.get("prior_applications", [])
    prior_outcomes = ", ".join(p.get("recommendation", "?") for p in prior_apps[:5]) or "No prior history"

    prompt = template.format(
        customer_id=req.get("customerId", "unknown"),
        days_past_due=days_past_due,
        amount_past_due=req.get("amountPastDue", 0),
        current_balance=current_balance,
        credit_limit=current_limit,
        utilization=utilization,
        previous_treatments=req.get("previousTreatments", []) or "None",
        contact_attempts=req.get("contactAttempts", 0),
        consistency_score=profile.get("payment_consistency_score", 0.5),
        prior_outcomes=prior_outcomes,
    )

    floor_treatment = _dpd_floor(days_past_due)

    try:
        raw = await asyncio.to_thread(cached_llm_invoke, prompt)
        result = json.loads(raw)

        required = {"treatment", "urgency", "script_key", "escalation_required", "rationale"}
        if not required.issubset(result.keys()):
            raise ValueError(f"Missing fields: {required - result.keys()}")

        # Rules-based floor enforcement
        escalation_rank = {"REMINDER": 0, "HARDSHIP_PROGRAM": 1, "COLLECTIONS_REFERRAL": 2}
        if escalation_rank.get(result["treatment"], 0) < escalation_rank.get(floor_treatment, 0):
            logger.warning(
                "treatment_agent floor applied",
                correlation_id=corr,
                llm_treatment=result["treatment"],
                floor=floor_treatment,
            )
            result["treatment"] = floor_treatment

        latency = round(time.time() - start, 2)
        logger.info("treatment_agent complete", correlation_id=corr,
                    treatment=result["treatment"], urgency=result["urgency"],
                    latency_s=latency)

        rec_map = {
            "REMINDER":             "MANUAL_REVIEW",
            "HARDSHIP_PROGRAM":     "MANUAL_REVIEW",
            "COLLECTIONS_REFERRAL": "DECLINE",
        }

        return {
            "treatment_result": result,
            "risk_decision": {
                "recommendation":  rec_map.get(result["treatment"], "MANUAL_REVIEW"),
                "confidence":      0.9 if result["escalation_required"] else 0.75,
                "composite_score": 0.9 if result["escalation_required"] else 0.75,
                "reasons":         [result.get("rationale", "")],
                "strategy_version": "rules+llm",
                "signal_weights":  {},
                "treatment":       result["treatment"],
                "urgency":         result["urgency"],
            },
        }

    except Exception as exc:
        logger.error("treatment_agent failed - fallback", correlation_id=corr,
                     error_type=type(exc).__name__)
        return {
            "treatment_result": {
                "treatment": floor_treatment,
                "urgency": "MEDIUM",
                "script_key": "FALLBACK_SCRIPT",
                "escalation_required": True,
                "rationale": "Fallback treatment applied after agent error",
                "next_review_days": 7,
            },
            "risk_decision": {
                "recommendation":  "MANUAL_REVIEW",
                "confidence":      0.5,
                "composite_score": 0.5,
                "reasons":         ["Treatment agent fallback"],
                "strategy_version": "unknown",
                "signal_weights":  {},
            },
        }
