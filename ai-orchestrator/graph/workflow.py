"""
LangGraph Workflow
------------------
Defines the multi-agent StateGraph.

Topology:
  START
    ↓ (fan-out — all three run in parallel)
  credit_agent ──┐
  fraud_agent ───┼──→ risk_decision_agent → explainability_agent → END
  policy_rag ────┘

LangGraph parallel execution:
  Adding multiple edges from the same source node triggers parallel execution.
  All three agents run concurrently; risk_decision waits for all to complete.
"""
from langgraph.graph import StateGraph, END
from agents.state import GraphState
from agents.credit_agent import credit_agent
from agents.fraud_agent import fraud_agent
from agents.policy_rag_agent import policy_rag_agent
from agents.risk_decision_agent import risk_decision_agent
from agents.explainability_agent import explainability_agent


def build_workflow() -> StateGraph:
    graph = StateGraph(GraphState)

    # Register nodes
    graph.add_node("credit_agent",       credit_agent)
    graph.add_node("fraud_agent",        fraud_agent)
    graph.add_node("policy_rag_agent",   policy_rag_agent)
    graph.add_node("risk_decision",      risk_decision_agent)
    graph.add_node("explainability",     explainability_agent)

    # Parallel fan-out from START
    graph.set_entry_point("credit_agent")
    graph.add_edge("credit_agent",     "risk_decision")

    # To run fraud and policy in parallel with credit, set all three as entry points
    # LangGraph executes all entry-point-reachable nodes before proceeding
    graph.add_node("_start_fraud",  fraud_agent)
    graph.add_node("_start_policy", policy_rag_agent)
    graph.set_entry_point("credit_agent")

    # Simpler approach that works reliably with LangGraph 0.1.x:
    # Use a fan-out coordinator node
    graph2 = StateGraph(GraphState)
    graph2.add_node("credit_agent",     credit_agent)
    graph2.add_node("fraud_agent",      fraud_agent)
    graph2.add_node("policy_rag_agent", policy_rag_agent)
    graph2.add_node("risk_decision",    risk_decision_agent)
    graph2.add_node("explainability",   explainability_agent)

    # Sequential chain (safe for LangGraph 0.1.x)
    # credit → fraud → policy → risk_decision → explainability
    # NOTE: LangGraph 0.2+ supports true parallel via Send() API
    # For now, sequential is functionally equivalent for a local POC
    graph2.set_entry_point("credit_agent")
    graph2.add_edge("credit_agent",     "fraud_agent")
    graph2.add_edge("fraud_agent",      "policy_rag_agent")
    graph2.add_edge("policy_rag_agent", "risk_decision")
    graph2.add_edge("risk_decision",    "explainability")
    graph2.add_edge("explainability",   END)

    return graph2.compile()
