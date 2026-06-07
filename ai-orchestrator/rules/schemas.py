from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


class RuleDefinition(BaseModel):
    """Single rule entry. Extra YAML fields become condition parameter substitutions."""
    model_config = ConfigDict(extra="allow")

    name: str
    condition: str
    action: str                   # APPROVE | DECLINE | MANUAL_REVIEW
    priority: int = 10
    ecoa_code: str | None = None  # single ECOA code
    ecoa_codes: list[str] = []    # multiple ECOA codes (when a rule maps to > 1 code)

    def get_params(self) -> dict[str, Any]:
        """Extra fields used as {param} substitutions in the condition string."""
        return self.model_extra or {}

    @property
    def all_ecoa_codes(self) -> list[str]:
        codes = list(self.ecoa_codes)
        if self.ecoa_code and self.ecoa_code not in codes:
            codes.insert(0, self.ecoa_code)
        return codes


class CreditRules(BaseModel):
    version: str
    prompt_context: dict[str, Any] = {}
    rules: list[RuleDefinition]


class FraudRules(BaseModel):
    version: str
    prompt_context: dict[str, Any] = {}
    rules: list[RuleDefinition]


class PolicyRules(BaseModel):
    version: str
    rules: list[RuleDefinition]


class SynthesisWeights(BaseModel):
    version: str
    weights: dict[str, float]    # {credit: 0.45, fraud: 0.30, policy: 0.25}
    thresholds: dict[str, float] # {approve_below: 0.35, decline_above: 0.65}


class StrategyMetadata(BaseModel):
    version: str
    effective_date: str
    author: str
    changelog: list[str]


class RuleMatch(BaseModel):
    rule_name: str
    action: str
    ecoa_codes: list[str]
    priority: int
