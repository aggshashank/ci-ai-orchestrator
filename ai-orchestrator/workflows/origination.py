"""
Origination workflow — credit card application decisioning.

Topology:
  enrich_customer_context
        ↓
  credit_agent ──┐
  fraud_agent  ──┼──→ risk_decision_agent → explainability_agent
  policy_rag   ──┘

(Sequential in LangGraph 0.1.x; parallel via Send() API in 0.2+)
"""
from langgraph.graph import END, StateGraph

from agents.credit_agent import credit_agent
from agents.explainability_agent import explainability_agent
from agents.fraud_agent import fraud_agent
from agents.policy_rag_agent import policy_rag_agent
from agents.risk_decision_agent import risk_decision_agent
from agents.state import GraphState
from customer_context.enrichment import enrich_with_customer_context


class OriginationWorkflow:
    decision_type = "ORIGINATION"

    def build(self):
        graph = StateGraph(GraphState)

        graph.add_node("enrich_customer_context", enrich_with_customer_context)
        graph.add_node("credit_agent",            credit_agent)
        graph.add_node("fraud_agent",             fraud_agent)
        graph.add_node("policy_rag_agent",        policy_rag_agent)
        graph.add_node("risk_decision",           risk_decision_agent)
        graph.add_node("explainability",          explainability_agent)

        graph.set_entry_point("enrich_customer_context")
        graph.add_edge("enrich_customer_context", "credit_agent")
        graph.add_edge("credit_agent",            "fraud_agent")
        graph.add_edge("fraud_agent",             "policy_rag_agent")
        graph.add_edge("policy_rag_agent",        "risk_decision")
        graph.add_edge("risk_decision",           "explainability")
        graph.add_edge("explainability",          END)

        return graph.compile()
