"""
Credit risk agent (async).
"""
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


async def credit_agent(state: GraphState) -> dict:
    start = time.time()
    app = state["application"]
    corr = state["correlation_id"]

    logger.info("credit_agent start", correlation_id=corr)

    engine = get_engine_for_state(state)
    ctx = engine.get_credit_prompt_context()

    settings = get_settings()
    template = get_prompt_registry().get("credit_agent", settings.credit_agent_prompt_version)
    prompt = template.format(
        credit_score=app.creditScore,
        utilization=app.utilization,
        delinquencies=app.delinquencies or 0,
        score_decline=ctx.get("score_decline", 580),
        score_fair_max=ctx.get("score_fair_max", 669),
        score_good_min=ctx.get("score_good_min", 670),
        score_very_good_min=ctx.get("score_very_good_min", 740),
        score_very_good_min_minus1=ctx.get("score_very_good_min", 740) - 1,
        util_high=ctx.get("util_high", 80),
        util_medium=ctx.get("util_medium", 50),
        delinq_high=ctx.get("delinq_high", 3),
        delinq_medium=ctx.get("delinq_medium", 1),
    )

    try:
        raw = await asyncio.to_thread(cached_llm_invoke, prompt)
        result = json.loads(raw)

        required = {"riskLevel", "reason", "score", "keyFactors"}
        if not required.issubset(result.keys()):
            raise ValueError(f"Missing fields in LLM response: {required - result.keys()}")

        latency = round(time.time() - start, 2)
        logger.info(
            "credit_agent complete",
            correlation_id=corr,
            risk_level=result["riskLevel"],
            latency_s=latency,
        )
        return {"credit_result": result}

    except Exception as exc:
        logger.error(
            "credit_agent failed - using fallback",
            correlation_id=corr,
            error_type=type(exc).__name__,
        )
        return {
            "credit_result": {
                "riskLevel": "HIGH",
                "reason": "Credit agent fallback applied after processing error",
                "score": 1.0,
                "keyFactors": ["agent_error_fallback"],
            }
        }
