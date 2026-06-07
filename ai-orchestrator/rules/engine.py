"""
RulesEngine: evaluate YAML-defined rules against input signals.

Condition expressions are plain Python-like strings with {param} placeholders:
  "credit_score < {threshold}"  → threshold substituted from the rule's own fields
  "address_mismatch == true AND delinquencies >= {delinq_threshold}"

Safe evaluation uses Python's ast module — only Comparisons, BoolOps, Names,
and Constants are allowed. eval() is never called.
"""
from __future__ import annotations

import ast
import operator
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

import structlog

from rules.loader import RulesLoader, get_loader
from rules.schemas import RuleDefinition, RuleMatch

logger = structlog.get_logger()

# ── Safe expression evaluator ─────────────────────────────────────────────────

_COMPARE_OPS: dict[type, Any] = {
    ast.Lt:    operator.lt,
    ast.LtE:   operator.le,
    ast.Gt:    operator.gt,
    ast.GtE:   operator.ge,
    ast.Eq:    operator.eq,
    ast.NotEq: operator.ne,
}


def _normalise(expr: str) -> str:
    """Normalise condition string to valid Python before AST parsing."""
    expr = re.sub(r"\bAND\b", "and", expr)
    expr = re.sub(r"\bOR\b",  "or",  expr)
    expr = re.sub(r"\btrue\b",  "True",  expr)
    expr = re.sub(r"\bfalse\b", "False", expr)
    return expr


def _resolve_condition(rule: RuleDefinition) -> str:
    """Substitute {param} placeholders with values from rule's extra fields."""
    condition = rule.condition
    for key, val in rule.get_params().items():
        condition = condition.replace(f"{{{key}}}", str(val))
    return condition


def _eval_node(node: ast.expr, ctx: dict[str, Any]) -> Any:
    if isinstance(node, ast.Compare):
        left = _eval_node(node.left, ctx)
        for op, comparator in zip(node.ops, node.comparators):
            right = _eval_node(comparator, ctx)
            fn = _COMPARE_OPS.get(type(op))
            if fn is None:
                raise ValueError(f"Disallowed comparison operator: {type(op).__name__!r}")
            if not fn(left, right):
                return False
        return True
    if isinstance(node, ast.BoolOp):
        values = [_eval_node(v, ctx) for v in node.values]
        return all(values) if isinstance(node.op, ast.And) else any(values)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
        return not _eval_node(node.operand, ctx)
    if isinstance(node, ast.Name):
        if node.id not in ctx:
            raise ValueError(f"Unknown variable in rule condition: {node.id!r}")
        return ctx[node.id]
    if isinstance(node, ast.Constant):
        return node.value
    raise ValueError(f"Disallowed AST node in rule condition: {type(node).__name__!r}")


def _safe_eval(expr: str, ctx: dict[str, Any]) -> bool:
    """Evaluate a normalised condition expression against ctx. Never calls eval()."""
    try:
        tree = ast.parse(_normalise(expr), mode="eval")
    except SyntaxError as exc:
        raise ValueError(f"Invalid rule condition syntax: {expr!r}") from exc
    return bool(_eval_node(tree.body, ctx))


# ── RulesEngine ───────────────────────────────────────────────────────────────

class RulesEngine:
    def __init__(self, loader: RulesLoader, version: str) -> None:
        self._loader = loader
        self._version = version

    @property
    def strategy_version(self) -> str:
        return self._version

    # ── Rule evaluation ───────────────────────────────────────────────────────

    def evaluate_credit(
        self,
        credit_score: int,
        utilization: float,
        delinquencies: int,
    ) -> list[RuleMatch]:
        ctx = {
            "credit_score": credit_score,
            "utilization": utilization,
            "delinquencies": delinquencies,
            "address_mismatch": False,  # not a credit signal but some rules reference it
        }
        return self._match_rules(self._loader.get_credit_rules().rules, ctx)

    def evaluate_fraud(
        self,
        address_mismatch: bool,
        delinquencies: int,
        channel: str,
    ) -> list[RuleMatch]:
        ctx = {
            "address_mismatch": address_mismatch,
            "delinquencies": delinquencies,
            "channel": channel,
        }
        return self._match_rules(self._loader.get_fraud_rules().rules, ctx)

    def evaluate_policy(
        self,
        credit_score: int,
        utilization: float,
        address_mismatch: bool,
        delinquencies: int,
    ) -> list[RuleMatch]:
        ctx = {
            "credit_score": credit_score,
            "utilization": utilization,
            "address_mismatch": address_mismatch,
            "delinquencies": delinquencies,
        }
        return self._match_rules(self._loader.get_policy_rules().rules, ctx)

    # ── Configuration accessors ───────────────────────────────────────────────

    def get_weights(self) -> dict[str, float]:
        return self._loader.get_synthesis_weights().weights

    def get_decision_thresholds(self) -> dict[str, float]:
        return self._loader.get_synthesis_weights().thresholds

    def get_credit_prompt_context(self) -> dict[str, Any]:
        return self._loader.get_credit_rules().prompt_context

    def get_fraud_prompt_context(self) -> dict[str, Any]:
        return self._loader.get_fraud_rules().prompt_context

    def get_ecoa_codes(self) -> dict[str, tuple[str, str]]:
        """
        Return {rule_name: (primary_ecoa_code, description)} for all rules that
        carry ECOA codes. Used by explainability_agent to build adverse action lists.
        """
        mapping: dict[str, tuple[str, str]] = {}
        for loader_fn in (
            self._loader.get_credit_rules,
            self._loader.get_fraud_rules,
            self._loader.get_policy_rules,
        ):
            ruleset = loader_fn()
            for rule in ruleset.rules:
                codes = rule.all_ecoa_codes
                if codes:
                    mapping[rule.name] = (codes[0], rule.name.replace("_", " "))
        return mapping

    # ── Internal ──────────────────────────────────────────────────────────────

    def _match_rules(
        self, rules: list[RuleDefinition], ctx: dict[str, Any]
    ) -> list[RuleMatch]:
        matches: list[RuleMatch] = []
        for rule in sorted(rules, key=lambda r: r.priority):
            try:
                resolved = _resolve_condition(rule)
                if _safe_eval(resolved, ctx):
                    matches.append(
                        RuleMatch(
                            rule_name=rule.name,
                            action=rule.action,
                            ecoa_codes=rule.all_ecoa_codes,
                            priority=rule.priority,
                        )
                    )
            except Exception as exc:
                logger.warning(
                    "rule_eval_failed",
                    rule=rule.name,
                    error=str(exc),
                )
        return matches


# ── Factory ───────────────────────────────────────────────────────────────────

@lru_cache()
def get_rules_engine() -> RulesEngine:
    from config import get_settings  # local import avoids circular deps at module load

    settings = get_settings()
    strategies_dir = Path(__file__).parent.parent / settings.strategies_dir
    loader = get_loader(
        settings.strategy_version,
        strategies_dir,
        settings.redis_url,
    )
    return RulesEngine(loader, settings.strategy_version)
