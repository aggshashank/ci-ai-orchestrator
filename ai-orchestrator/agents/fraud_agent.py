"""
Fraud risk agent (async).
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


async def fraud_agent(state: GraphState) -> dict:
    start = time.time()
    app = state["application"]
    corr = state["correlation_id"]

    logger.info("fraud_agent start", correlation_id=corr)

    engine = get_engine_for_state(state)
    ctx = engine.get_fraud_prompt_context()

    settings = get_settings()
    template = get_prompt_registry().get("fraud_agent", settings.fraud_agent_prompt_version)
    prompt = template.format(
        address_mismatch=str(app.addressMismatch).lower(),
        delinquencies=app.delinquencies or 0,
        channel=app.channel or "WEB",
        delinq_combined_threshold=ctx.get("delinq_combined_threshold", 2),
        delinq_any_threshold=ctx.get("delinq_any_threshold", 1),
    )

    try:
        raw = await asyncio.to_thread(cached_llm_invoke, prompt)
        result = json.loads(raw)

        required = {"fraudRisk", "reason", "indicators", "recommendAction"}
        if not required.issubset(result.keys()):
            raise ValueError(f"Missing fields: {required - result.keys()}")

        latency = round(time.time() - start, 2)
        logger.info(
            "fraud_agent complete",
            correlation_id=corr,
            fraud_risk=result["fraudRisk"],
            latency_s=latency,
        )
        return {"fraud_result": result}

    except Exception as exc:
        logger.error(
            "fraud_agent failed - using fallback",
            correlation_id=corr,
            error_type=type(exc).__name__,
        )
        return {
            "fraud_result": {
                "fraudRisk": "MEDIUM",
                "reason": "Fraud agent fallback applied after processing error",
                "indicators": ["agent_error_fallback"],
                "recommendAction": "MANUAL_REVIEW",
            }
        }
