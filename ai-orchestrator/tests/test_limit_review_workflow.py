"""
Limit Review workflow — golden dataset tests.

The deterministic DPD floor and risk_decision mapping are tested without LLMs.
LLM-dependent recommendation tests mock the LLM response and verify the
limit_review_agent correctly builds risk_decision from it.
"""
from __future__ import annotations

import json
import pytest
from unittest.mock import MagicMock, patch
from conftest import load_dataset

DATASET = load_dataset("limit_review")


class TestLimitReviewAgent:
    def _make_state(self, case: dict) -> dict:
        return {
            "correlation_id": case["id"],
            "decision_type": "LIMIT_REVIEW",
            "limit_review_request": case["input"],
            "customer_profile": case.get("profile", {}),
            "experiment_variant": "",
        }

    def _mock_llm_response(self, recommendation: str, change_pct: int,
                           current_limit: float) -> dict:
        return {
            "recommendation": recommendation,
            "suggested_change_pct": change_pct,
            "suggested_new_limit": current_limit * (1 + change_pct / 100),
            "confidence": 0.85,
            "reasons": ["Test reason"],
            "risk_factors": [],
        }

    @pytest.mark.parametrize("case", DATASET, ids=[c["id"] for c in DATASET])
    def test_recommendation_mapping(self, case):
        """Verify INCREASE→APPROVE, MAINTAIN→MANUAL_REVIEW, DECREASE→DECLINE mapping."""
        from agents.limit_review_agent import limit_review_agent

        expected = case["expected_recommendation"]
        current_limit = case["input"]["currentCreditLimit"]

        llm_resp = self._mock_llm_response(
            recommendation=expected,
            change_pct=25 if expected == "INCREASE" else (-20 if expected == "DECREASE" else 0),
            current_limit=current_limit,
        )

        with patch("agents.limit_review_agent.get_llm") as mock_get_llm, \
             patch("agents.limit_review_agent.get_prompt_registry") as mock_reg, \
             patch("agents.limit_review_agent.get_engine_for_state") as mock_engine:

            mock_get_llm.return_value.invoke.return_value = json.dumps(llm_resp)
            mock_reg.return_value.get.return_value = (
                "Review limit. {customer_id} {current_limit} {account_age_months} "
                "{utilization_avg} {payment_rate} {payments_on_time} {payments_total} "
                "{missed_payments} {current_balance} {consistency_score} "
                "{util_trend} {prior_outcomes} {estimated_clv}"
            )
            mock_engine.return_value.strategy_version = "v1.0.0"

            state = self._make_state(case)
            result = limit_review_agent(state)

        assert "limit_review_result" in result
        assert "risk_decision" in result

        rec_map = {"INCREASE": "APPROVE", "MAINTAIN": "MANUAL_REVIEW", "DECREASE": "DECLINE"}
        expected_rec = rec_map[expected]
        assert result["risk_decision"]["recommendation"] == expected_rec, \
            f"{case['id']}: expected risk_decision.recommendation={expected_rec}"

    def test_fallback_on_llm_failure(self):
        """LLM exception should produce MAINTAIN/MANUAL_REVIEW fallback."""
        from agents.limit_review_agent import limit_review_agent

        state = {
            "correlation_id": "test-fallback",
            "decision_type": "LIMIT_REVIEW",
            "limit_review_request": {"customerId": "C1", "currentCreditLimit": 5000,
                                      "accountAgeMonths": 12, "recentUtilizationAvg": 50,
                                      "paymentsMadeOnTime": 12, "paymentsCounted": 12,
                                      "missedPayments": 0, "currentBalance": 2500},
            "customer_profile": {},
            "experiment_variant": "",
        }

        with patch("agents.limit_review_agent.get_llm") as mock_get_llm, \
             patch("agents.limit_review_agent.get_prompt_registry") as mock_reg, \
             patch("agents.limit_review_agent.get_engine_for_state"):

            mock_get_llm.return_value.invoke.side_effect = RuntimeError("LLM offline")
            mock_reg.return_value.get.return_value = "template {customer_id} {current_limit} {account_age_months} {utilization_avg} {payment_rate} {payments_on_time} {payments_total} {missed_payments} {current_balance} {consistency_score} {util_trend} {prior_outcomes} {estimated_clv}"

            result = limit_review_agent(state)

        assert result["limit_review_result"]["recommendation"] == "MAINTAIN"
        assert result["risk_decision"]["recommendation"] == "MANUAL_REVIEW"
