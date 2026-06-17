"""
Limit Review workflow — monthly credit limit reassessment.

Topology:
  enrich_customer_context → limit_review_agent → explainability_agent
"""
from langgraph.graph import END, StateGraph

from agents.explainability_agent import explainability_agent
from agents.limit_review_agent import limit_review_agent
from agents.state import GraphState
from customer_context.enrichment import enrich_with_customer_context


class LimitReviewWorkflow:
    decision_type = "LIMIT_REVIEW"

    def build(self):
        graph = StateGraph(GraphState)

        graph.add_node("enrich_customer_context", enrich_with_customer_context)
        graph.add_node("limit_review_agent",      limit_review_agent)
        graph.add_node("explainability",          explainability_agent)

        graph.set_entry_point("enrich_customer_context")
        graph.add_edge("enrich_customer_context", "limit_review_agent")
        graph.add_edge("limit_review_agent",      "explainability")
        graph.add_edge("explainability",          END)

        return graph.compile()
