"""
WorkflowRouter — maps decision_type → compiled LangGraph.

Graphs are built once and cached for the lifetime of the process.
Each graph is built lazily on first request so startup stays fast.
"""
from __future__ import annotations

import threading
from typing import Any

import structlog

logger = structlog.get_logger()

_lock = threading.Lock()
_cache: dict[str, Any] = {}


def get_workflow(decision_type: str):
    """Return the compiled LangGraph for decision_type. Thread-safe, lazy."""
    if decision_type in _cache:
        return _cache[decision_type]

    with _lock:
        if decision_type in _cache:
            return _cache[decision_type]

        graph = _build(decision_type)
        _cache[decision_type] = graph
        logger.info("workflow_compiled", decision_type=decision_type)
        return graph


def _build(decision_type: str):
    if decision_type == "ORIGINATION":
        from workflows.origination import OriginationWorkflow
        return OriginationWorkflow().build()

    if decision_type == "LIMIT_REVIEW":
        from workflows.limit_review import LimitReviewWorkflow
        return LimitReviewWorkflow().build()

    if decision_type == "DELINQUENCY_TREATMENT":
        from workflows.delinquency import DelinquencyWorkflow
        return DelinquencyWorkflow().build()

    if decision_type == "CROSS_SELL":
        from workflows.cross_sell import CrossSellWorkflow
        return CrossSellWorkflow().build()

    raise ValueError(f"Unknown decision_type: {decision_type!r}")
