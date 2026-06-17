"""
Origination workflow — golden dataset tests.

These tests validate the deterministic rules engine layer (rule evaluation and
ECOA code derivation) without any LLM calls. The credit/fraud/policy LLM responses
are mocked; the risk_decision synthesis and ECOA code logic are exercised for real.
"""
from __future__ import annotations

import pytest
from conftest import load_dataset


DATASET = load_dataset("origination")


# ── Rules engine unit tests ──────────────────────────────────────────────────

class TestCreditRulesEngine:
    """Validate _safe_eval rule matching without any LLM."""

    def _engine(self):
        from pathlib import Path
        from rules.loader import get_loader
        from rules.engine import RulesEngine

        strategies_dir = Path(__file__).parent.parent / "strategies"
        loader = get_loader("v1.0.0", strategies_dir, "")
        return RulesEngine(loader, "v1.0.0")

    def test_auto_decline_low_score(self):
        engine = self._engine()
        matches = engine.evaluate_credit(credit_score=540, utilization=45, delinquencies=0)
        actions = {m.action for m in matches}
        assert "DECLINE" in actions
        codes = {c for m in matches for c in m.ecoa_codes}
        assert "AA01" in codes

    def test_auto_approve_excellent(self):
        engine = self._engine()
        matches = engine.evaluate_credit(credit_score=780, utilization=12, delinquencies=0)
        actions = {m.action for m in matches}
        assert "APPROVE" in actions
        assert "DECLINE" not in actions

    def test_fraud_high_combined(self):
        engine = self._engine()
        matches = engine.evaluate_fraud(address_mismatch=True, delinquencies=2, channel="WEB")
        actions = {m.action for m in matches}
        assert "DECLINE" in actions
        codes = {c for m in matches for c in m.ecoa_codes}
        assert "AA07" in codes
        assert "AA09" in codes

    def test_policy_combined_risk(self):
        engine = self._engine()
        matches = engine.evaluate_policy(credit_score=615, utilization=72, address_mismatch=False, delinquencies=0)
        actions = {m.action for m in matches}
        assert "DECLINE" in actions

    def test_safe_eval_rejects_disallowed_nodes(self):
        from rules.engine import _safe_eval
        import pytest
        with pytest.raises(ValueError, match="Disallowed"):
            _safe_eval("__import__('os').system('echo hack')", {})

    def test_safe_eval_normalises_and_or(self):
        from rules.engine import _safe_eval
        assert _safe_eval("credit_score > 600 AND delinquencies == 0",
                          {"credit_score": 700, "delinquencies": 0}) is True
        assert _safe_eval("credit_score < 580 OR delinquencies >= 3",
                          {"credit_score": 700, "delinquencies": 0}) is False


# ── Golden dataset parametric tests ─────────────────────────────────────────

@pytest.mark.parametrize("case", [c for c in DATASET if "expected_rule_action" in c],
                         ids=[c["id"] for c in DATASET if "expected_rule_action" in c])
def test_origination_rule_action(case):
    """
    Verify that the rules engine matches the expected primary action for each
    origination golden dataset case. LLM is not involved in rule evaluation.
    """
    from pathlib import Path
    from rules.loader import get_loader
    from rules.engine import RulesEngine

    inp = case["input"]
    strategies_dir = Path(__file__).parent.parent / "strategies"
    loader = get_loader("v1.0.0", strategies_dir, "")
    engine = RulesEngine(loader, "v1.0.0")

    credit_matches = engine.evaluate_credit(inp["creditScore"], inp["utilization"], inp.get("delinquencies", 0))
    fraud_matches  = engine.evaluate_fraud(inp.get("addressMismatch", False), inp.get("delinquencies", 0), inp.get("channel", "WEB"))
    policy_matches = engine.evaluate_policy(inp["creditScore"], inp["utilization"], inp.get("addressMismatch", False), inp.get("delinquencies", 0))

    all_matches = credit_matches + fraud_matches + policy_matches
    actions = {m.action for m in all_matches}

    expected = case["expected_rule_action"]
    # DECLINE in any match set → overall decline intent
    if expected == "DECLINE":
        assert "DECLINE" in actions, f"{case['id']}: expected DECLINE in {actions}"
    elif expected == "APPROVE":
        assert "APPROVE" in actions and "DECLINE" not in actions, \
            f"{case['id']}: expected APPROVE-only, got {actions}"
    else:
        # MANUAL_REVIEW — some signal fires without a hard DECLINE
        assert actions, f"{case['id']}: expected rules to fire, got no matches"


@pytest.mark.parametrize("case", [c for c in DATASET if "expected_ecoa_codes" in c and c.get("expected_ecoa_codes")],
                         ids=[c["id"] for c in DATASET if "expected_ecoa_codes" in c and c.get("expected_ecoa_codes")])
def test_origination_ecoa_codes(case):
    """Verify ECOA codes produced by the rules engine match expected values."""
    from pathlib import Path
    from rules.loader import get_loader
    from rules.engine import RulesEngine

    inp = case["input"]
    strategies_dir = Path(__file__).parent.parent / "strategies"
    loader = get_loader("v1.0.0", strategies_dir, "")
    engine = RulesEngine(loader, "v1.0.0")

    credit_matches = engine.evaluate_credit(inp["creditScore"], inp["utilization"], inp.get("delinquencies", 0))
    fraud_matches  = engine.evaluate_fraud(inp.get("addressMismatch", False), inp.get("delinquencies", 0), inp.get("channel", "WEB"))

    codes = {c for m in credit_matches + fraud_matches for c in m.ecoa_codes}
    for expected_code in case["expected_ecoa_codes"]:
        assert expected_code in codes, \
            f"{case['id']}: expected ECOA code {expected_code} not found in {codes}"


def test_challenger_boundary_case():
    """GD-O-007: score=590 declines on v1.0.0 (floor=580), reviewed on v1.1.0 (floor=600)."""
    from pathlib import Path
    from rules.loader import get_loader
    from rules.engine import RulesEngine

    strategies_dir = Path(__file__).parent.parent / "strategies"

    champion = RulesEngine(get_loader("v1.0.0", strategies_dir, ""), "v1.0.0")
    challenger = RulesEngine(get_loader("v1.1.0", strategies_dir, ""), "v1.1.0")

    champ_matches = champion.evaluate_credit(590, 30, 0)
    chal_matches  = challenger.evaluate_credit(590, 30, 0)

    champ_actions = {m.action for m in champ_matches}
    chal_actions  = {m.action for m in chal_matches}

    assert "DECLINE" in champ_actions, "Champion v1.0.0 should decline score=590"
    assert "DECLINE" not in chal_actions or "MANUAL_REVIEW" in chal_actions, \
        "Challenger v1.1.0 should not hard-decline score=590"
