"""
Fraud risk agent.
"""
import json
import time

import structlog

from agents.state import GraphState
from llm.factory import get_llm
from rules.engine import get_rules_engine

logger = structlog.get_logger()

# Threshold placeholders are filled at call time from fraud_rules.yaml prompt_context.
FRAUD_PROMPT = """\
You are a fraud analyst for a fintech company. Analyze this application for fraud risk.

Application signals:
- Address Mismatch: {address_mismatch} (billing address does not match bureau records)
- Delinquency Count: {delinquencies} (recent late payments, possible identity theft signal)
- Application Channel: {channel}

Return ONLY a JSON object with exactly these fields:
{{
  "fraudRisk": "HIGH" or "MEDIUM" or "LOW",
  "reason": "one sentence explanation",
  "indicators": ["list", "of", "specific", "risk", "signals"],
  "recommendAction": "PROCEED" or "MANUAL_REVIEW" or "DECLINE"
}}

Rules:
- fraudRisk HIGH if: address_mismatch is true AND delinquencies >= {delinq_combined_threshold}
- fraudRisk MEDIUM if: address_mismatch is true OR delinquencies >= {delinq_any_threshold}
- fraudRisk LOW if: address_mismatch is false AND delinquencies == 0
- recommendAction DECLINE only if fraudRisk HIGH and strong indicators
"""


def fraud_agent(state: GraphState) -> dict:
    start = time.time()
    app = state["application"]
    corr = state["correlation_id"]

    logger.info("fraud_agent start", correlation_id=corr)

    engine = get_rules_engine()
    ctx = engine.get_fraud_prompt_context()
    prompt = FRAUD_PROMPT.format(
        address_mismatch=str(app.addressMismatch).lower(),
        delinquencies=app.delinquencies or 0,
        channel=app.channel or "WEB",
        delinq_combined_threshold=ctx.get("delinq_combined_threshold", 2),
        delinq_any_threshold=ctx.get("delinq_any_threshold", 1),
    )

    try:
        llm = get_llm()
        raw = llm.invoke(prompt)
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
