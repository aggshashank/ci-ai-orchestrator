"""
format_scorer.py — validates structural correctness of agent JSON output.

Score: 1.0 = perfect, 0.0 = unparseable JSON. Partial deductions for each violation.
"""
import json, re
from dataclasses import dataclass, field

AGENT_SCHEMAS = {
    "credit_agent": {
        "required_keys": ["riskLevel", "reason", "score", "keyFactors"],
        "enums": {"riskLevel": {"HIGH", "MEDIUM", "LOW"}},
        "types": {"score": (int, float), "keyFactors": list},
    },
    "fraud_agent": {
        "required_keys": ["fraudRisk", "reason", "indicators", "recommendAction"],
        "enums": {
            "fraudRisk": {"HIGH", "MEDIUM", "LOW"},
            "recommendAction": {"PROCEED", "MANUAL_REVIEW", "DECLINE"},
        },
        "types": {"indicators": list},
    },
    "policy_rag_agent": {
        "required_keys": ["policy_applicable", "rules", "action", "citations"],
        "enums": {"action": {"APPROVE", "MANUAL_REVIEW", "DECLINE"}},
        "types": {"policy_applicable": bool, "rules": list, "citations": list},
    },
    "risk_decision_agent": {
        "required_keys": ["recommendation", "confidence", "reasons"],
        "enums": {"recommendation": {"APPROVE", "MANUAL_REVIEW", "DECLINE"}},
        "types": {"confidence": (int, float), "reasons": list},
    },
    "explainability_agent": {
        "required_keys": ["plain_language_summary", "audit_narrative", "recommended_next_steps"],
        "enums": {},
        "types": {},
    },
}

MD_PATTERN = re.compile(r"```|^\s*#", re.MULTILINE)


@dataclass
class FormatScore:
    agent: str
    score: float
    passed: bool
    issues: list = field(default_factory=list)
    parsed: dict = field(default_factory=dict)


def score_format(agent_name: str, raw_output: str) -> FormatScore:
    issues = []
    deductions = 0.0
    text = raw_output.strip()

    # Markdown contamination
    if MD_PATTERN.search(text):
        issues.append("Output contains markdown fences or headings")
        deductions += 0.20
        m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        if m:
            text = m.group(1)
        else:
            brace = text.find("{")
            if brace >= 0:
                text = text[brace:]

    # JSON parse
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        return FormatScore(agent=agent_name, score=0.0, passed=False,
                           issues=[f"Invalid JSON: {str(e)[:120]}"])

    schema = AGENT_SCHEMAS.get(agent_name, {})

    for key in schema.get("required_keys", []):
        if key not in data:
            issues.append(f"Missing required key: '{key}'")
            deductions += 0.20

    for fld, allowed in schema.get("enums", {}).items():
        if fld in data and data[fld] not in allowed:
            issues.append(f"'{fld}'='{data[fld]}' not in {allowed}")
            deductions += 0.25

    for fld, expected in schema.get("types", {}).items():
        if fld in data and not isinstance(data[fld], expected):
            issues.append(f"'{fld}' expected {expected}, got {type(data[fld]).__name__}")
            deductions += 0.15

    score = round(max(0.0, 1.0 - deductions), 3)
    return FormatScore(agent=agent_name, score=score,
                       passed=score >= 0.95, issues=issues, parsed=data)
