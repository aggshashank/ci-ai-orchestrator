"""
Risk Decision Agent
-------------------
Synthesises outputs from all three parallel agents into a final recommendation.
This is a deterministic aggregator — uses weighted scoring, not another LLM call.

Why deterministic here?
  Using an LLM to combine three LLM outputs adds non-determinism and cost.
  For a regulated fintech system, the synthesis logic should be auditable and
  reproducible. A weighted rule is both faster and explainable to a regulator.
"""
import time
import structlog
from agents.state import GraphState
from rules.engine import get_engine_for_state

logger = structlog.get_logger()

# Risk level → numeric score (not configurable — these are semantic mappings)
RISK_SCORES = {"HIGH": 1.0, "MEDIUM": 0.5, "LOW": 0.0}

# Action to numeric score for policy agent
POLICY_ACTION_SCORES = {"DECLINE": 1.0, "MANUAL_REVIEW": 0.5, "APPROVE": 0.0}


def risk_decision_agent(state: GraphState) -> dict:
    start = time.time()
    corr = state["correlation_id"]

    credit = state.get("credit_result", {})
    fraud = state.get("fraud_result", {})
    policy = state.get("policy_context", {})

    engine = get_engine_for_state(state)
    weights = engine.get_weights()
    thresholds = engine.get_decision_thresholds()
    approve_below = thresholds.get("approve_below", 0.35)
    decline_above = thresholds.get("decline_above", 0.65)

    logger.info("risk_decision_agent start", correlation_id=corr,
                credit_risk=credit.get("riskLevel"),
                fraud_risk=fraud.get("fraudRisk"),
                policy_action=policy.get("action"),
                strategy_version=engine.strategy_version)

    # --- Weighted confidence score ---
    credit_score = RISK_SCORES.get(credit.get("riskLevel", "HIGH"), 1.0)
    fraud_score = RISK_SCORES.get(fraud.get("fraudRisk", "HIGH"), 1.0)
    policy_score = POLICY_ACTION_SCORES.get(policy.get("action", "MANUAL_REVIEW"), 0.5)

    composite = (
        credit_score * weights["credit"] +
        fraud_score  * weights["fraud"] +
        policy_score * weights["policy"]
    )

    # --- Decision routing ---
    # Hard DECLINE overrides (both primary agents flagging HIGH)
    if credit.get("riskLevel") == "HIGH" and fraud.get("fraudRisk") == "HIGH":
        recommendation = "DECLINE"
        confidence = round(composite, 2)
    elif credit.get("riskLevel") == "LOW" and fraud.get("fraudRisk") == "LOW" and \
            policy.get("action") == "APPROVE":
        recommendation = "APPROVE"
        confidence = round(1.0 - composite, 2)
    elif composite >= decline_above:
        recommendation = "DECLINE"
        confidence = round(composite, 2)
    elif composite >= approve_below:
        recommendation = "MANUAL_REVIEW"
        confidence = round(composite, 2)
    else:
        recommendation = "APPROVE"
        confidence = round(1.0 - composite, 2)

    # --- Collect reasons ---
    reasons = []
    if credit.get("reason"):
        reasons.append(f"Credit: {credit['reason']}")
    if fraud.get("reason"):
        reasons.append(f"Fraud: {fraud['reason']}")
    if policy.get("rules"):
        reasons.extend([f"Policy: {r}" for r in policy["rules"][:2]])

    result = {
        "recommendation": recommendation,
        "confidence": confidence,
        "composite_score": round(composite, 3),
        "strategy_version": engine.strategy_version,
        "reasons": reasons,
        "signal_weights": {
            "credit_contribution": round(credit_score * weights["credit"], 3),
            "fraud_contribution": round(fraud_score * weights["fraud"], 3),
            "policy_contribution": round(policy_score * weights["policy"], 3),
        },
    }

    latency = round(time.time() - start, 2)
    logger.info("risk_decision_agent complete", correlation_id=corr,
                recommendation=recommendation, confidence=confidence,
                strategy_version=engine.strategy_version,
                latency_s=latency)

    return {"risk_decision": result}
