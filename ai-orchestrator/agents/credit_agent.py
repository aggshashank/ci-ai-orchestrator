"""
Credit Risk Agent
-----------------
Analyses credit score, utilization, and delinquencies.
Returns structured JSON risk assessment.

Llama 3.1 JSON prompting notes:
  - Be VERY explicit: "Return ONLY a JSON object. No explanation. No markdown."
  - List the exact fields and types you expect
  - Low temperature (0.0) ensures consistent structured output
  - format="json" in Ollama enforces JSON token sampling
"""
import json
import time
import structlog
from agents.state import GraphState
from llm.factory import get_llm

logger = structlog.get_logger()

CREDIT_PROMPT = """\
You are a credit risk analyst for a fintech company. Analyze this credit application data.

Application data:
- Credit Score: {credit_score} (FICO range 300-850; below 580=poor, 580-669=fair, 670-739=good, 740+=very good)
- Revolving Utilization: {utilization}% (above 30% is concerning; above 80% is high risk)
- Delinquencies (past 2 years): {delinquencies}

Return ONLY a JSON object with exactly these fields:
{{
  "riskLevel": "HIGH" or "MEDIUM" or "LOW",
  "reason": "one sentence explanation",
  "score": a float between 0.0 (lowest risk) and 1.0 (highest risk),
  "keyFactors": ["factor1", "factor2"]
}}

Rules:
- riskLevel HIGH if: credit score < 580 OR utilization > 80 OR delinquencies >= 3
- riskLevel MEDIUM if: credit score 580-669 OR utilization 50-80 OR delinquencies 1-2
- riskLevel LOW if: credit score >= 670 AND utilization < 50 AND delinquencies == 0
"""


def credit_agent(state: GraphState) -> dict:
    start = time.time()
    app = state["application"]
    corr = state["correlation_id"]

    logger.info("credit_agent start", correlation_id=corr,
                credit_score=app.creditScore, utilization=app.utilization)

    prompt = CREDIT_PROMPT.format(
        credit_score=app.creditScore,
        utilization=app.utilization,
        delinquencies=app.delinquencies or 0,
    )

    try:
        llm = get_llm()
        raw = llm.invoke(prompt)
        result = json.loads(raw)

        # Validate required fields — Llama occasionally omits a key
        required = {"riskLevel", "reason", "score", "keyFactors"}
        if not required.issubset(result.keys()):
            raise ValueError(f"Missing fields in LLM response: {required - result.keys()}")

        latency = round(time.time() - start, 2)
        logger.info("credit_agent complete", correlation_id=corr,
                    risk_level=result["riskLevel"], latency_s=latency)
        return {"credit_result": result}

    except Exception as e:
        logger.error("credit_agent failed — using fallback",
                     correlation_id=corr, error=str(e))
        # Fail-safe: treat as HIGH risk → will route to MANUAL_REVIEW
        return {"credit_result": {
            "riskLevel": "HIGH",
            "reason": f"Credit agent error — fallback applied: {str(e)}",
            "score": 1.0,
            "keyFactors": ["agent_error_fallback"],
        }}
