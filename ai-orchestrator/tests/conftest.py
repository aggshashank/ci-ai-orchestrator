"""
Shared fixtures for workflow golden dataset tests.

LLM calls are mocked at the llm.factory level so tests are fully deterministic
and run without a live Ollama/Groq/OpenAI connection.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

_DATASETS = Path(__file__).parent / "golden_datasets"


def load_dataset(name: str) -> list[dict]:
    path = _DATASETS / f"{name}.json"
    return json.loads(path.read_text())


@pytest.fixture
def mock_llm(monkeypatch):
    """
    Returns a factory that configures the mocked LLM to return a specific JSON response.
    Usage:
        mock_llm({"riskLevel": "LOW", "reason": "test", "score": 0.1, "keyFactors": []})
    """
    captured = {}

    def _setup(response_dict: dict) -> MagicMock:
        llm = MagicMock()
        llm.invoke.return_value = json.dumps(response_dict)
        captured["llm"] = llm
        monkeypatch.setattr("llm.factory.get_llm", lambda: llm)
        return llm

    return _setup


@pytest.fixture
def mock_prompt_registry(monkeypatch, tmp_path):
    """
    Creates temporary prompt files and patches the registry to use them.
    Each agent gets a minimal passthrough template.
    """
    agents = [
        ("credit_agent",        "v1", "You are a credit analyst. {credit_score} {utilization} {delinquencies} {score_decline} {score_fair_max} {score_good_min} {score_very_good_min} {score_very_good_min_minus1} {util_high} {util_medium} {delinq_high} {delinq_medium}"),
        ("fraud_agent",         "v1", "You are a fraud analyst. {address_mismatch} {delinquencies} {channel} {delinq_combined_threshold} {delinq_any_threshold}"),
        ("policy_rag_agent",    "v1", "You are a policy officer. {credit_score} {utilization} {address_mismatch} {delinquencies} {policy_chunks}"),
        ("explainability_agent","v1", "Explain the decision. {recommendation} {confidence} {credit_risk} {credit_reason} {fraud_risk} {fraud_reason} {policy_rules}"),
        ("limit_review_agent",  "v1", "Review limit. {customer_id} {current_limit} {account_age_months} {utilization_avg} {payment_rate} {payments_on_time} {payments_total} {missed_payments} {current_balance} {consistency_score} {util_trend} {prior_outcomes} {estimated_clv}"),
        ("treatment_agent",     "v1", "Select treatment. {customer_id} {days_past_due} {amount_past_due} {current_balance} {credit_limit} {utilization} {previous_treatments} {contact_attempts} {consistency_score} {prior_outcomes}"),
        ("propensity_agent",    "v1", "Score propensity. {customer_id} {months_on_book} {current_product} {avg_monthly_balance} {annual_spend} {reward_points} {trigger_reason} {consistency_score} {estimated_clv} {prior_outcomes}"),
    ]

    for agent_name, version, content in agents:
        agent_dir = tmp_path / agent_name
        agent_dir.mkdir(parents=True, exist_ok=True)
        (agent_dir / f"{version}.txt").write_text(content)

    from prompts.registry import PromptRegistry, get_prompt_registry
    registry = PromptRegistry(tmp_path)
    monkeypatch.setattr("prompts.registry.get_prompt_registry", lambda: registry)

    # Also patch each agent module's direct import
    import agents.credit_agent as ca
    import agents.fraud_agent as fa
    import agents.policy_rag_agent as pra
    import agents.explainability_agent as ea
    import agents.limit_review_agent as lra
    import agents.treatment_agent as ta
    import agents.propensity_agent as pa

    for mod in [ca, fa, pra, ea, lra, ta, pa]:
        monkeypatch.setattr(mod, "get_prompt_registry", lambda: registry)

    return registry
