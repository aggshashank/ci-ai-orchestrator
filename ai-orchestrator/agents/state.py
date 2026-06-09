"""
GraphState — the single typed dict that flows through every LangGraph node.
Each agent reads what it needs and writes only its own output key.
LangGraph merges partial dicts — never mutate state in place.
"""
from typing import TypedDict, Optional, Any
from models.events import ApplicationRequest


class GraphState(TypedDict, total=False):
    # Set at intake
    correlation_id: str
    application: ApplicationRequest

    # Agent outputs (populated in parallel)
    credit_result: dict       # {riskLevel, reason, score}
    fraud_result: dict        # {fraudRisk, reason, indicators}
    policy_context: dict      # {rules, action, policy_applicable}

    # Synthesis (populated after fan-in)
    risk_decision: dict       # {recommendation, confidence, reasons}

    # Explainability (final node)
    explanation: dict         # {plain_language_summary, adverse_action_codes,
                              #  audit_narrative, policy_citations, signal_weights}
    # Experiment routing — set by consumer before graph.invoke()
    experiment_variant: str     # "champion" | "challenger" | ""
    prompt_versions: dict       # populated by explainability_agent at final node

    # Error propagation
    error: Optional[str]
