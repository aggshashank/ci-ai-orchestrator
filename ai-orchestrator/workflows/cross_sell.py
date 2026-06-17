"""
Cross-Sell workflow — post-onboarding product propensity scoring.

Topology:
  enrich_customer_context → propensity_agent → explainability_agent
"""
from langgraph.graph import END, StateGraph

from agents.explainability_agent import explainability_agent
from agents.propensity_agent import propensity_agent
from agents.state import GraphState
from customer_context.enrichment import enrich_with_customer_context


class CrossSellWorkflow:
    decision_type = "CROSS_SELL"

    def build(self):
        graph = StateGraph(GraphState)

        graph.add_node("enrich_customer_context", enrich_with_customer_context)
        graph.add_node("propensity_agent",        propensity_agent)
        graph.add_node("explainability",          explainability_agent)

        graph.set_entry_point("enrich_customer_context")
        graph.add_edge("enrich_customer_context", "propensity_agent")
        graph.add_edge("propensity_agent",        "explainability")
        graph.add_edge("explainability",          END)

        return graph.compile()
