"""
Delinquency Treatment workflow — golden dataset tests.

Key deterministic behaviour: the DPD floor rule must override the LLM if it
attempts to de-escalate below the minimum treatment for the DPD band.
"""
from __future__ import annotations

import json
import pytest
from unittest.mock import patch
from conftest import load_dataset

DATASET = load_dataset("delinquency")


class TestTreatmentDPDFloor:
    """Unit tests for the deterministic DPD floor logic (no LLM involved)."""

    def test_floor_0_14_dpd(self):
        from agents.treatment_agent import _dpd_floor
        assert _dpd_floor(0)  == "REMINDER"
        assert _dpd_floor(7)  == "REMINDER"
        assert _dpd_floor(14) == "REMINDER"

    def test_floor_15_59_dpd(self):
        from agents.treatment_agent import _dpd_floor
        assert _dpd_floor(15) == "HARDSHIP_PROGRAM"
        assert _dpd_floor(40) == "HARDSHIP_PROGRAM"
        assert _dpd_floor(59) == "HARDSHIP_PROGRAM"

    def test_floor_60_plus_dpd(self):
        from agents.treatment_agent import _dpd_floor
        assert _dpd_floor(60)  == "COLLECTIONS_REFERRAL"
        assert _dpd_floor(75)  == "COLLECTIONS_REFERRAL"
        assert _dpd_floor(180) == "COLLECTIONS_REFERRAL"

    def test_floor_enforced_over_llm(self):
        """LLM returning REMINDER for 65 DPD should be overridden to COLLECTIONS_REFERRAL."""
        from agents.treatment_agent import treatment_agent

        llm_resp = {
            "treatment": "REMINDER",       # LLM de-escalating incorrectly
            "urgency": "LOW",
            "script_key": "STANDARD_REMINDER",
            "escalation_required": False,
            "rationale": "Customer has no prior treatments",
            "next_review_days": 7,
        }

        state = {
            "correlation_id": "floor-test",
            "decision_type": "DELINQUENCY_TREATMENT",
            "delinquency_request": {
                "customerId": "C1",
                "daysPastDue": 65,
                "amountPastDue": 1000.0,
                "currentBalance": 5000.0,
                "currentCreditLimit": 8000.0,
                "previousTreatments": [],
                "contactAttempts": 1,
            },
            "customer_profile": {"payment_consistency_score": 0.5, "prior_applications": []},
            "experiment_variant": "",
        }

        with patch("agents.treatment_agent.get_llm") as mock_get_llm, \
             patch("agents.treatment_agent.get_prompt_registry") as mock_reg:

            mock_get_llm.return_value.invoke.return_value = json.dumps(llm_resp)
            mock_reg.return_value.get.return_value = (
                "template {customer_id} {days_past_due} {amount_past_due} "
                "{current_balance} {credit_limit} {utilization} "
                "{previous_treatments} {contact_attempts} {consistency_score} {prior_outcomes}"
            )

            result = treatment_agent(state)

        # Floor must win over LLM
        assert result["treatment_result"]["treatment"] == "COLLECTIONS_REFERRAL", \
            "DPD floor must override LLM de-escalation at 65 DPD"


@pytest.mark.parametrize("case", DATASET, ids=[c["id"] for c in DATASET])
def test_delinquency_expected_treatment(case):
    """
    Verify treatment outcome for each golden dataset case.
    For cases where the DPD floor determines the answer, the LLM response
    agrees; for GD-DT-005 the floor overrides.
    """
    from agents.treatment_agent import treatment_agent

    req = case["input"]
    expected = case["expected_treatment"]

    llm_resp = {
        "treatment": expected,
        "urgency": case.get("expected_urgency", "MEDIUM"),
        "script_key": f"SCRIPT_{expected}",
        "escalation_required": expected == "COLLECTIONS_REFERRAL",
        "rationale": f"Golden dataset case {case['id']}",
        "next_review_days": 7,
    }

    state = {
        "correlation_id": case["id"],
        "decision_type": "DELINQUENCY_TREATMENT",
        "delinquency_request": req,
        "customer_profile": case.get("profile", {"payment_consistency_score": 0.5, "prior_applications": []}),
        "experiment_variant": "",
    }

    with patch("agents.treatment_agent.get_llm") as mock_get_llm, \
         patch("agents.treatment_agent.get_prompt_registry") as mock_reg:

        mock_get_llm.return_value.invoke.return_value = json.dumps(llm_resp)
        mock_reg.return_value.get.return_value = (
            "template {customer_id} {days_past_due} {amount_past_due} "
            "{current_balance} {credit_limit} {utilization} "
            "{previous_treatments} {contact_attempts} {consistency_score} {prior_outcomes}"
        )

        result = treatment_agent(state)

    assert result["treatment_result"]["treatment"] == expected, \
        f"{case['id']}: expected treatment={expected}, got {result['treatment_result']['treatment']}"
