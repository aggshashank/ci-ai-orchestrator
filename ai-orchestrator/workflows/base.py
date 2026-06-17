"""
BaseWorkflow protocol — every workflow must satisfy this interface.
Callers obtain a compiled LangGraph via build() and call graph.invoke(state).
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable

from langgraph.graph import CompiledGraph


@runtime_checkable
class BaseWorkflow(Protocol):
    decision_type: str

    def build(self) -> CompiledGraph: ...


VALID_DECISION_TYPES = frozenset({
    "ORIGINATION",
    "LIMIT_REVIEW",
    "DELINQUENCY_TREATMENT",
    "CROSS_SELL",
})
