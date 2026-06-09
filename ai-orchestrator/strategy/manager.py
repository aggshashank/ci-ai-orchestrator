"""
StrategyManager: snapshot YAML files, create engine from a stored snapshot.

SnapshotLoader wraps a plain dict (loaded from DB JSONB) and satisfies the
same interface as RulesLoader so RulesEngine is unaware of the source.
"""
from __future__ import annotations

from typing import Any

from rules.engine import RulesEngine, get_rules_engine
from rules.schemas import (
    CreditRules,
    FraudRules,
    PolicyRules,
    StrategyMetadata,
    SynthesisWeights,
)


class SnapshotLoader:
    """
    Read-only rules loader backed by a pre-loaded dict rather than YAML files.
    Used for replay and simulation so results are reproducible from the DB snapshot.
    """

    def __init__(self, snapshot: dict[str, Any]) -> None:
        self._credit = CreditRules.model_validate(snapshot["credit_rules"])
        self._fraud = FraudRules.model_validate(snapshot["fraud_rules"])
        self._policy = PolicyRules.model_validate(snapshot["policy_rules"])
        self._weights = SynthesisWeights.model_validate(snapshot["synthesis_weights"])

    def get_credit_rules(self) -> CreditRules:
        return self._credit

    def get_fraud_rules(self) -> FraudRules:
        return self._fraud

    def get_policy_rules(self) -> PolicyRules:
        return self._policy

    def get_synthesis_weights(self) -> SynthesisWeights:
        return self._weights

    def get_metadata(self) -> StrategyMetadata:
        raise NotImplementedError("SnapshotLoader does not carry metadata.")

    def invalidate(self, key: str | None = None) -> None:
        pass  # snapshots are immutable


def take_snapshot() -> dict[str, Any]:
    """
    Serialise all rules through the active rules engine into a JSON-safe dict.
    This is the format stored in strategy_versions.rules_snapshot.
    """
    engine = get_rules_engine()
    loader = engine._loader
    return {
        "credit_rules": loader.get_credit_rules().model_dump(),
        "fraud_rules": loader.get_fraud_rules().model_dump(),
        "policy_rules": loader.get_policy_rules().model_dump(),
        "synthesis_weights": loader.get_synthesis_weights().model_dump(),
    }


def engine_from_snapshot(snapshot: dict[str, Any], version: str) -> RulesEngine:
    """Create a RulesEngine that reads exclusively from a stored snapshot."""
    return RulesEngine(SnapshotLoader(snapshot), version)


def score_deterministically(
    engine: RulesEngine,
    credit: dict[str, Any],
    fraud: dict[str, Any],
    policy: dict[str, Any],
) -> tuple[str, float, float]:
    """
    Re-run the risk_decision_agent scoring formula using a specific engine.
    Returns (recommendation, confidence, composite_score).
    Duplicated here intentionally — simulation must be insulated from agent refactors.
    """
    _RISK = {"HIGH": 1.0, "MEDIUM": 0.5, "LOW": 0.0}
    _POLICY = {"DECLINE": 1.0, "MANUAL_REVIEW": 0.5, "APPROVE": 0.0}

    w = engine.get_weights()
    t = engine.get_decision_thresholds()

    cs = _RISK.get(credit.get("riskLevel", "HIGH"), 1.0)
    fs = _RISK.get(fraud.get("fraudRisk", "HIGH"), 1.0)
    ps = _POLICY.get(policy.get("action", "MANUAL_REVIEW"), 0.5)

    composite = cs * w["credit"] + fs * w["fraud"] + ps * w["policy"]

    if credit.get("riskLevel") == "HIGH" and fraud.get("fraudRisk") == "HIGH":
        rec = "DECLINE"
        conf = round(composite, 2)
    elif (
        credit.get("riskLevel") == "LOW"
        and fraud.get("fraudRisk") == "LOW"
        and policy.get("action") == "APPROVE"
    ):
        rec = "APPROVE"
        conf = round(1.0 - composite, 2)
    elif composite >= t.get("decline_above", 0.65):
        rec = "DECLINE"
        conf = round(composite, 2)
    elif composite >= t.get("approve_below", 0.35):
        rec = "MANUAL_REVIEW"
        conf = round(composite, 2)
    else:
        rec = "APPROVE"
        conf = round(1.0 - composite, 2)

    return rec, conf, round(composite, 3)
