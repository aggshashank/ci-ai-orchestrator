from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class StrategyVersionRecord(BaseModel):
    """API-facing representation of a registered strategy version."""
    version: str
    is_active: bool
    activated_at: datetime | None
    deactivated_at: datetime | None
    created_at: datetime
    changelog: list[str]
    rules_snapshot: dict[str, Any]
    weights_snapshot: dict[str, float]


class RuleDiff(BaseModel):
    """Change to a single rule between two strategy versions."""
    rule_name: str
    change_type: str              # "added" | "removed" | "modified"
    before: dict[str, Any] | None
    after: dict[str, Any] | None


class StrategyDiff(BaseModel):
    from_version: str
    to_version: str
    rule_changes: list[RuleDiff]  # across credit, fraud, policy rule lists
    weight_changes: dict[str, dict[str, float]]    # {credit: {before: 0.45, after: 0.50}}
    threshold_changes: dict[str, dict[str, float]] # {approve_below: {before: 0.35, after: 0.30}}
    has_breaking_changes: bool    # any DECLINE rules added/tightened
    summary: str
