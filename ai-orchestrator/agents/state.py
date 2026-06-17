"""
GraphState — the single typed dict that flows through every LangGraph node.
Each agent reads what it needs and writes only its own output key.
LangGraph merges partial dicts — never mutate state in place.
"""
from typing import TypedDict, Optional, Any
from models.events import ApplicationRequest


class GraphState(TypedDict, total=False):
    # ── Routing ───────────────────────────────────────────────────────────────
    correlation_id: str
    decision_type: str          # ORIGINATION | LIMIT_REVIEW | DELINQUENCY_TREATMENT | CROSS_SELL

    # ── Intake payloads (one is populated depending on decision_type) ─────────
    application: ApplicationRequest         # ORIGINATION
    limit_review_request: dict              # LIMIT_REVIEW
    delinquency_request: dict              # DELINQUENCY_TREATMENT
    cross_sell_request: dict               # CROSS_SELL

    # ── Customer 360 (populated by enrichment node for all workflow types) ────
    customer_id: str
    customer_profile: dict                 # CustomerProfile.model_dump()
    customer_context_version: str          # profile_version timestamp

    # ── Origination agent outputs ─────────────────────────────────────────────
    credit_result: dict       # {riskLevel, reason, score}
    fraud_result: dict        # {fraudRisk, reason, indicators}
    policy_context: dict      # {rules, action, policy_applicable}

    # ── Workflow-specific outputs ─────────────────────────────────────────────
    limit_review_result: dict  # {recommendation, suggested_change_pct, ...}
    treatment_result: dict     # {treatment, urgency, script_key, escalation_required}
    propensity_result: dict    # {recommended_product, propensity_score, eligible_products}

    # ── Synthesis (all workflow types) ────────────────────────────────────────
    risk_decision: dict       # {recommendation, confidence, reasons, strategy_version}

    # ── Explainability (final node for all workflow types) ────────────────────
    explanation: dict

    # ── Experiment routing — set by consumer before graph.invoke() ────────────
    experiment_variant: str   # "champion" | "challenger" | ""
    prompt_versions: dict     # populated by explainability_agent at final node

    # ── Error propagation ─────────────────────────────────────────────────────
    error: Optional[str]
