"""
Credit risk agent.
"""
import json
import time

import structlog

from agents.state import GraphState
from llm.factory import get_llm
from rules.engine import get_rules_engine

logger = structlog.get_logger()

# Threshold placeholders are filled at call time from credit_rules.yaml prompt_context.
CREDIT_PROMPT = """\
You are a credit risk analyst for a fintech company. Analyze this credit application data.

Application data:
- Credit Score: {credit_score} (FICO range 300-850; below {score_decline}=poor, \
{score_decline}-{score_fair_max}=fair, {score_good_min}-{score_very_good_min_minus1}=good, \
{score_very_good_min}+=very good)
- Revolving Utilization: {utilization}% (above 30% is concerning; above {util_high}% is high risk)
- Delinquencies (past 2 years): {delinquencies}

Return ONLY a JSON object with exactly these fields:
{{
  "riskLevel": "HIGH" or "MEDIUM" or "LOW",
  "reason": "one sentence explanation",
  "score": a float between 0.0 (lowest risk) and 1.0 (highest risk),
  "keyFactors": ["factor1", "factor2"]
}}

Rules:
- riskLevel HIGH if: credit score < {score_decline} OR utilization > {util_high} OR \
delinquencies >= {delinq_high}
- riskLevel MEDIUM if: credit score {score_decline}-{score_fair_max} OR \
utilization {util_medium}-{util_high} OR delinquencies {delinq_medium}-{delinq_high}
- riskLevel LOW if: credit score >= {score_good_min} AND utilization < {util_medium} \
AND delinquencies == 0
"""


def credit_agent(state: GraphState) -> dict:
    start = time.time()
    app = state["application"]
    corr = state["correlation_id"]

    logger.info("credit_agent start", correlation_id=corr)

    engine = get_rules_engine()
    ctx = engine.get_credit_prompt_context()
    prompt = CREDIT_PROMPT.format(
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
        llm = get_llm()
        raw = llm.invoke(prompt)
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
