"""
diff_strategies: compare two strategy snapshots and produce a human-readable diff.

A snapshot dict has the shape:
  {
    "credit_rules":  {"version": "...", "rules": [...], "prompt_context": {...}},
    "fraud_rules":   {"version": "...", "rules": [...]},
    "policy_rules":  {"version": "...", "rules": [...]},
    "synthesis_weights": {"version": "...", "weights": {...}, "thresholds": {...}},
  }
"""
from __future__ import annotations

from typing import Any

from strategy.models import RuleDiff, StrategyDiff

_RULE_SETS = ("credit_rules", "fraud_rules", "policy_rules")

# Actions that, when added or made stricter, constitute a breaking change.
_DECLINE_ACTIONS = {"DECLINE"}


def diff_strategies(
    from_version: str,
    from_snapshot: dict[str, Any],
    to_version: str,
    to_snapshot: dict[str, Any],
) -> StrategyDiff:
    rule_changes = _diff_all_rule_sets(from_snapshot, to_snapshot)
    weight_changes = _diff_numeric_section(
        from_snapshot.get("synthesis_weights", {}).get("weights", {}),
        to_snapshot.get("synthesis_weights", {}).get("weights", {}),
    )
    threshold_changes = _diff_numeric_section(
        from_snapshot.get("synthesis_weights", {}).get("thresholds", {}),
        to_snapshot.get("synthesis_weights", {}).get("thresholds", {}),
    )
    breaking = _is_breaking(rule_changes, weight_changes, threshold_changes)
    summary = _summarise(rule_changes, weight_changes, threshold_changes, breaking)

    return StrategyDiff(
        from_version=from_version,
        to_version=to_version,
        rule_changes=rule_changes,
        weight_changes=weight_changes,
        threshold_changes=threshold_changes,
        has_breaking_changes=breaking,
        summary=summary,
    )


# ── Internal helpers ──────────────────────────────────────────────────────────

def _diff_all_rule_sets(
    before_snap: dict[str, Any],
    after_snap: dict[str, Any],
) -> list[RuleDiff]:
    diffs: list[RuleDiff] = []
    for section in _RULE_SETS:
        before_rules = before_snap.get(section, {}).get("rules", [])
        after_rules = after_snap.get(section, {}).get("rules", [])
        for d in _diff_rule_list(before_rules, after_rules, prefix=section):
            diffs.append(d)
    return diffs


def _diff_rule_list(
    before: list[dict[str, Any]],
    after: list[dict[str, Any]],
    prefix: str,
) -> list[RuleDiff]:
    before_map = {r["name"]: r for r in before}
    after_map = {r["name"]: r for r in after}
    diffs: list[RuleDiff] = []

    for name in before_map.keys() - after_map.keys():
        diffs.append(RuleDiff(
            rule_name=f"{prefix}.{name}",
            change_type="removed",
            before=before_map[name],
            after=None,
        ))
    for name in after_map.keys() - before_map.keys():
        diffs.append(RuleDiff(
            rule_name=f"{prefix}.{name}",
            change_type="added",
            before=None,
            after=after_map[name],
        ))
    for name in before_map.keys() & after_map.keys():
        if before_map[name] != after_map[name]:
            diffs.append(RuleDiff(
                rule_name=f"{prefix}.{name}",
                change_type="modified",
                before=before_map[name],
                after=after_map[name],
            ))

    return sorted(diffs, key=lambda d: d.rule_name)


def _diff_numeric_section(
    before: dict[str, float],
    after: dict[str, float],
) -> dict[str, dict[str, float]]:
    changes: dict[str, dict[str, float]] = {}
    all_keys = set(before) | set(after)
    for key in all_keys:
        b = before.get(key)
        a = after.get(key)
        if b != a:
            changes[key] = {"before": b, "after": a}
    return changes


def _is_breaking(
    rule_changes: list[RuleDiff],
    weight_changes: dict,
    threshold_changes: dict,
) -> bool:
    for diff in rule_changes:
        if diff.change_type == "added" and diff.after and diff.after.get("action") in _DECLINE_ACTIONS:
            return True
        if diff.change_type == "modified":
            # Condition tightened → hard to detect generically; flag any DECLINE change
            if diff.after and diff.after.get("action") in _DECLINE_ACTIONS:
                return True
    # Raising decline_above threshold means fewer declines (not breaking)
    # Lowering approve_below threshold means fewer approvals (potentially breaking)
    if "approve_below" in threshold_changes:
        b = threshold_changes["approve_below"].get("before", 0.35)
        a = threshold_changes["approve_below"].get("after", 0.35)
        if a > b:
            return True
    return False


def _summarise(
    rule_changes: list[RuleDiff],
    weight_changes: dict,
    threshold_changes: dict,
    breaking: bool,
) -> str:
    parts: list[str] = []
    added = sum(1 for d in rule_changes if d.change_type == "added")
    removed = sum(1 for d in rule_changes if d.change_type == "removed")
    modified = sum(1 for d in rule_changes if d.change_type == "modified")
    if added:
        parts.append(f"{added} rule(s) added")
    if removed:
        parts.append(f"{removed} rule(s) removed")
    if modified:
        parts.append(f"{modified} rule(s) modified")
    if weight_changes:
        parts.append(f"{len(weight_changes)} weight(s) changed")
    if threshold_changes:
        parts.append(f"{len(threshold_changes)} threshold(s) changed")
    if not parts:
        return "No changes between versions."
    prefix = "BREAKING: " if breaking else ""
    return prefix + "; ".join(parts) + "."
