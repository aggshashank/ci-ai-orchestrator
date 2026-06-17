"""
Delinquency Treatment workflow — event-driven; fires on payment_missed.

Topology:
  enrich_customer_context → treatment_agent → explainability_agent
"""
from langgraph.graph import END, StateGraph

from agents.explainability_agent import explainability_agent
from agents.state import GraphState
from agents.treatment_agent import treatment_agent
from customer_context.enrichment import enrich_with_customer_context


class DelinquencyWorkflow:
    decision_type = "DELINQUENCY_TREATMENT"

    def build(self):
        graph = StateGraph(GraphState)

        graph.add_node("enrich_customer_context", enrich_with_customer_context)
        graph.add_node("treatment_agent",         treatment_agent)
        graph.add_node("explainability",          explainability_agent)

        graph.set_entry_point("enrich_customer_context")
        graph.add_edge("enrich_customer_context", "treatment_agent")
        graph.add_edge("treatment_agent",         "explainability")
        graph.add_edge("explainability",          END)

        return graph.compile()
