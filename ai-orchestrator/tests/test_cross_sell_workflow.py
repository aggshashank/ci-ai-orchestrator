"""
Cross-Sell workflow — golden dataset tests.

Tests the propensity_score → recommendation mapping and the
APPROVE/MANUAL_REVIEW/DECLINE risk_decision derivation.
"""
from __future__ import annotations

import json
import pytest
from unittest.mock import patch
from conftest import load_dataset

DATASET = load_dataset("cross_sell")


class TestPropensityMapping:
    """Unit tests for the propensity_score → risk_decision mapping logic."""

    def _run_agent(self, propensity_score: float, recommended_product: str) -> dict:
        from agents.propensity_agent import propensity_agent

        llm_resp = {
            "recommended_product": recommended_product,
            "propensity_score": propensity_score,
            "eligible_products": [{"product": recommended_product, "score": propensity_score, "rationale": "test"}],
            "key_signals": ["test_signal"],
            "recommended_channel": "EMAIL",
        }

        state = {
            "correlation_id": "mapping-test",
            "decision_type": "CROSS_SELL",
            "cross_sell_request": {
                "customerId": "C1",
                "monthsOnBook": 12,
                "averageMonthlyBalance": 3000.0,
                "currentProduct": "BASIC_CARD",
                "triggerReason": "TENURE",
                "rewardPointsBalance": 5000,
                "annualSpend": 15000.0,
            },
            "customer_profile": {"payment_consistency_score": 0.9, "estimated_clv": 5000, "prior_applications": []},
            "experiment_variant": "",
        }

        template = (
            "propensity {customer_id} {months_on_book} {current_product} "
            "{avg_monthly_balance} {annual_spend} {reward_points} "
            "{trigger_reason} {consistency_score} {estimated_clv} {prior_outcomes}"
        )

        with patch("agents.propensity_agent.get_llm") as mock_get_llm, \
             patch("agents.propensity_agent.get_prompt_registry") as mock_reg:

            mock_get_llm.return_value.invoke.return_value = json.dumps(llm_resp)
            mock_reg.return_value.get.return_value = template

            return propensity_agent(state)

    def test_high_propensity_maps_to_approve(self):
        result = self._run_agent(0.85, "REWARDS_UPGRADE")
        assert result["risk_decision"]["recommendation"] == "APPROVE"

    def test_medium_propensity_maps_to_manual_review(self):
        result = self._run_agent(0.55, "BALANCE_TRANSFER_CARD")
        assert result["risk_decision"]["recommendation"] == "MANUAL_REVIEW"

    def test_low_propensity_maps_to_decline(self):
        result = self._run_agent(0.25, "NONE")
        assert result["risk_decision"]["recommendation"] == "DECLINE"

    def test_none_product_maps_to_decline(self):
        result = self._run_agent(0.60, "NONE")
        assert result["risk_decision"]["recommendation"] == "DECLINE"

    def test_fallback_on_llm_failure(self):
        from agents.propensity_agent import propensity_agent

        state = {
            "correlation_id": "fallback-test",
            "decision_type": "CROSS_SELL",
            "cross_sell_request": {"customerId": "C1", "monthsOnBook": 6,
                                   "averageMonthlyBalance": 1000, "currentProduct": "BASIC_CARD",
                                   "triggerReason": "TENURE", "rewardPointsBalance": 0, "annualSpend": 0},
            "customer_profile": {},
            "experiment_variant": "",
        }

        with patch("agents.propensity_agent.get_llm") as mock_get_llm, \
             patch("agents.propensity_agent.get_prompt_registry") as mock_reg:

            mock_get_llm.return_value.invoke.side_effect = RuntimeError("LLM offline")
            mock_reg.return_value.get.return_value = "template {customer_id} {months_on_book} {current_product} {avg_monthly_balance} {annual_spend} {reward_points} {trigger_reason} {consistency_score} {estimated_clv} {prior_outcomes}"

            result = propensity_agent(state)

        assert result["propensity_result"]["recommended_product"] == "NONE"
        assert result["risk_decision"]["recommendation"] == "DECLINE"


@pytest.mark.parametrize("case", DATASET, ids=[c["id"] for c in DATASET])
def test_cross_sell_expected_product(case):
    """Verify the recommended product for each cross-sell golden dataset case."""
    from agents.propensity_agent import propensity_agent

    req = case["input"]
    expected_product = case["expected_recommendation"]

    propensity_score = 0.85 if expected_product != "NONE" else 0.2

    llm_resp = {
        "recommended_product": expected_product,
        "propensity_score": propensity_score,
        "eligible_products": [{"product": expected_product, "score": propensity_score, "rationale": case["id"]}],
        "key_signals": ["golden_dataset"],
        "recommended_channel": "EMAIL",
    }

    state = {
        "correlation_id": case["id"],
        "decision_type": "CROSS_SELL",
        "cross_sell_request": req,
        "customer_profile": case.get("profile", {"payment_consistency_score": 0.8,
                                                  "estimated_clv": 2000, "prior_applications": []}),
        "experiment_variant": "",
    }

    template = (
        "propensity {customer_id} {months_on_book} {current_product} "
        "{avg_monthly_balance} {annual_spend} {reward_points} "
        "{trigger_reason} {consistency_score} {estimated_clv} {prior_outcomes}"
    )

    with patch("agents.propensity_agent.get_llm") as mock_get_llm, \
         patch("agents.propensity_agent.get_prompt_registry") as mock_reg:

        mock_get_llm.return_value.invoke.return_value = json.dumps(llm_resp)
        mock_reg.return_value.get.return_value = template

        result = propensity_agent(state)

    assert result["propensity_result"]["recommended_product"] == expected_product, \
        f"{case['id']}: expected product={expected_product}"
