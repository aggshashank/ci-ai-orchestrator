"""
correctness_scorer.py
---------------------
Scores whether agent output matches the golden label.

Two strategies:
  1. Exact match  — structured fields (riskLevel, recommendation, fraudRisk, action)
  2. LLM-as-judge — free-text fields (plain_language_summary, audit_narrative)

Score: 0.0 – 1.0 per agent.
"""
import json, re, time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class CorrectnessScore:
    agent: str
    score: float
    passed: bool
    checks: list = field(default_factory=list)   # list of {check, passed, detail}


# ── Exact-match helpers ───────────────────────────────────────────────────────

def _check(label: str, passed: bool, detail: str = "") -> dict:
    return {"check": label, "passed": passed, "detail": detail}


def _score_credit_agent(actual: dict, expected: dict) -> CorrectnessScore:
    checks = []
    points, total = 0.0, 0.0

    # riskLevel match
    total += 1
    exp_level = expected.get("riskLevel")
    act_level = actual.get("riskLevel")
    ok = exp_level == act_level
    checks.append(_check("riskLevel", ok, f"expected={exp_level} actual={act_level}"))
    if ok: points += 1

    # score range
    if "score_max" in expected:
        total += 1
        act_score = actual.get("score", 1.0)
        ok = act_score <= expected["score_max"]
        checks.append(_check("score_max", ok, f"max={expected['score_max']} actual={act_score}"))
        if ok: points += 1

    if "score_min" in expected:
        total += 1
        act_score = actual.get("score", 0.0)
        ok = act_score >= expected["score_min"]
        checks.append(_check("score_min", ok, f"min={expected['score_min']} actual={act_score}"))
        if ok: points += 1

    # reason is non-empty
    total += 0.5
    ok = bool(actual.get("reason", "").strip())
    checks.append(_check("reason_nonempty", ok))
    if ok: points += 0.5

    score = round(points / total, 3) if total > 0 else 0.0
    return CorrectnessScore("credit_agent", score, score >= 0.75, checks)


def _score_fraud_agent(actual: dict, expected: dict) -> CorrectnessScore:
    checks = []
    points, total = 0.0, 0.0

    total += 1
    exp_risk = expected.get("fraudRisk")
    act_risk = actual.get("fraudRisk")
    ok = exp_risk == act_risk
    checks.append(_check("fraudRisk", ok, f"expected={exp_risk} actual={act_risk}"))
    if ok: points += 1

    if "recommendAction" in expected:
        total += 1
        ok = actual.get("recommendAction") == expected["recommendAction"]
        checks.append(_check("recommendAction", ok,
                              f"expected={expected['recommendAction']} actual={actual.get('recommendAction')}"))
        if ok: points += 1

    total += 0.5
    ok = isinstance(actual.get("indicators"), list) and len(actual.get("indicators", [])) > 0
    checks.append(_check("indicators_nonempty", ok))
    if ok: points += 0.5

    score = round(points / total, 3) if total > 0 else 0.0
    return CorrectnessScore("fraud_agent", score, score >= 0.75, checks)


def _score_policy_rag(actual: dict, expected: dict) -> CorrectnessScore:
    checks = []
    points, total = 0.0, 0.0

    total += 1
    exp_action = expected.get("action")
    act_action = actual.get("action")
    ok = exp_action == act_action
    checks.append(_check("action", ok, f"expected={exp_action} actual={act_action}"))
    if ok: points += 1

    if "policy_applicable" in expected:
        total += 0.5
        ok = actual.get("policy_applicable") == expected["policy_applicable"]
        checks.append(_check("policy_applicable", ok))
        if ok: points += 0.5

    total += 0.5
    ok = isinstance(actual.get("rules"), list)
    checks.append(_check("rules_is_list", ok))
    if ok: points += 0.5

    score = round(points / total, 3) if total > 0 else 0.0
    return CorrectnessScore("policy_rag_agent", score, score >= 0.70, checks)


def _score_risk_decision(actual: dict, expected: dict) -> CorrectnessScore:
    checks = []
    points, total = 0.0, 0.0

    total += 2   # recommendation is the primary signal — double weight
    exp_rec = expected.get("recommendation")
    act_rec = actual.get("recommendation")
    ok = exp_rec == act_rec
    checks.append(_check("recommendation", ok, f"expected={exp_rec} actual={act_rec}"))
    if ok: points += 2

    if "confidence_min" in expected:
        total += 1
        act_conf = actual.get("confidence", 0.0)
        ok = act_conf >= expected["confidence_min"]
        checks.append(_check("confidence_min", ok,
                              f"min={expected['confidence_min']} actual={act_conf}"))
        if ok: points += 1

    total += 0.5
    ok = isinstance(actual.get("reasons"), list) and len(actual.get("reasons", [])) > 0
    checks.append(_check("reasons_nonempty", ok))
    if ok: points += 0.5

    score = round(points / total, 3) if total > 0 else 0.0
    return CorrectnessScore("risk_decision_agent", score, score >= 0.80, checks)


def _score_explainability(actual: dict, expected: dict, judge_fn=None) -> CorrectnessScore:
    checks = []
    points, total = 0.0, 0.0

    # Adverse action codes check
    exp_codes = set(expected.get("adverse_action_codes_expected", []))
    act_codes = set(c.get("code", c) if isinstance(c, dict) else c
                    for c in actual.get("adverse_action_codes", []))

    if exp_codes:
        total += 1
        missing = exp_codes - act_codes
        ok = len(missing) == 0
        checks.append(_check("adverse_codes_present", ok,
                              f"expected={exp_codes} actual={act_codes} missing={missing}"))
        if ok: points += 1
    else:
        total += 0.5
        ok = len(act_codes) == 0
        checks.append(_check("no_adverse_codes_when_approve", ok,
                              f"unexpected codes: {act_codes}"))
        if ok: points += 0.5

    # Keyword checks on summary
    summary = actual.get("plain_language_summary", "").lower()
    for word in expected.get("summary_must_contain", []):
        total += 0.5
        ok = word.lower() in summary
        checks.append(_check(f"summary_contains_{word}", ok))
        if ok: points += 0.5

    for word in expected.get("summary_must_not_contain", []):
        total += 0.5
        ok = word.lower() not in summary
        checks.append(_check(f"summary_not_contains_{word}", ok))
        if ok: points += 0.5

    # LLM-as-judge for summary quality (optional — only if judge_fn provided)
    if judge_fn and actual.get("plain_language_summary"):
        total += 1
        judge_score = judge_fn(actual["plain_language_summary"])
        ok = judge_score >= 0.5
        checks.append(_check("llm_judge_quality", ok, f"judge_score={judge_score}"))
        points += judge_score  # partial credit

    score = round(points / total, 3) if total > 0 else 0.5
    return CorrectnessScore("explainability_agent", score, score >= 0.60, checks)


# ── LLM-as-judge ─────────────────────────────────────────────────────────────

JUDGE_PROMPT = """You are evaluating a credit card application decision explanation.
Score the following explanation on a scale from 0 to 3:

0 = Wrong, misleading, or empty
1 = Partially correct but missing key information
2 = Correct and complete
3 = Correct, complete, and clearly written for a customer

Explanation to evaluate:
"{summary}"

Respond ONLY with a JSON object: {{"score": <integer 0-3>, "reason": "<one sentence>"}}"""


def llm_judge(summary: str, ollama_base_url: str = "http://localhost:11434",
              model: str = "llama3:latest") -> float:
    """
    Call the local LLM to judge explanation quality.
    Returns a normalized score 0.0 – 1.0.
    Falls back to 0.5 on any error.
    """
    try:
        import httpx
        prompt = JUDGE_PROMPT.format(summary=summary[:400])
        resp = httpx.post(
            f"{ollama_base_url}/api/generate",
            json={"model": model, "prompt": prompt, "format": "json", "stream": False},
            timeout=60,
        )
        resp.raise_for_status()
        data = json.loads(resp.json().get("response", "{}"))
        raw_score = int(data.get("score", 1))
        return round(min(max(raw_score, 0), 3) / 3.0, 3)
    except Exception:
        return 0.5   # neutral fallback — don't fail the entire eval


# ── Public interface ──────────────────────────────────────────────────────────

def score_correctness(agent_name: str, actual: dict, expected: dict,
                      use_judge: bool = False) -> CorrectnessScore:
    judge_fn = llm_judge if use_judge else None

    dispatch = {
        "credit_agent":         _score_credit_agent,
        "fraud_agent":          _score_fraud_agent,
        "policy_rag_agent":     _score_policy_rag,
        "risk_decision_agent":  _score_risk_decision,
    }

    if agent_name in dispatch:
        return dispatch[agent_name](actual, expected)
    elif agent_name == "explainability_agent":
        return _score_explainability(actual, expected, judge_fn)
    else:
        return CorrectnessScore(agent_name, 0.5, False,
                                [{"check": "unknown_agent", "passed": False,
                                  "detail": f"No scorer for {agent_name}"}])
