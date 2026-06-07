"""
JSON Schema validation for rules YAML files.
Called by the loader before Pydantic parsing so invalid YAML fails fast
with a clear schema error rather than a confusing Pydantic one.
"""
from __future__ import annotations

import jsonschema

_RULE_ITEM = {
    "type": "object",
    "required": ["name", "condition", "action"],
    "properties": {
        "name":       {"type": "string"},
        "condition":  {"type": "string"},
        "action":     {"type": "string", "enum": ["APPROVE", "DECLINE", "MANUAL_REVIEW"]},
        "priority":   {"type": "integer", "minimum": 1},
        "ecoa_code":  {"type": "string", "pattern": "^AA\\d{2}$"},
        "ecoa_codes": {
            "type": "array",
            "items": {"type": "string", "pattern": "^AA\\d{2}$"},
        },
    },
    "additionalProperties": True,  # allow threshold params (e.g. threshold: 580)
}

_RULES_BASE = {
    "type": "object",
    "required": ["version", "rules"],
    "properties": {
        "version":       {"type": "string"},
        "prompt_context": {"type": "object"},
        "rules": {
            "type": "array",
            "minItems": 1,
            "items": _RULE_ITEM,
        },
    },
    "additionalProperties": False,
}

CREDIT_RULES_SCHEMA: dict = {
    **_RULES_BASE,
    "properties": {
        **_RULES_BASE["properties"],
        "prompt_context": {
            "type": "object",
            "properties": {
                "score_decline":      {"type": "number"},
                "score_fair_max":     {"type": "number"},
                "score_good_min":     {"type": "number"},
                "score_very_good_min":{"type": "number"},
                "util_high":          {"type": "number"},
                "util_medium":        {"type": "number"},
                "delinq_high":        {"type": "number"},
                "delinq_medium":      {"type": "number"},
            },
        },
    },
}

FRAUD_RULES_SCHEMA: dict = {**_RULES_BASE}

POLICY_RULES_SCHEMA: dict = {**_RULES_BASE, "properties": {
    "version": {"type": "string"},
    "rules": _RULES_BASE["properties"]["rules"],
}}

SYNTHESIS_WEIGHTS_SCHEMA: dict = {
    "type": "object",
    "required": ["version", "weights", "thresholds"],
    "additionalProperties": False,
    "properties": {
        "version": {"type": "string"},
        "weights": {
            "type": "object",
            "required": ["credit", "fraud", "policy"],
            "properties": {
                "credit": {"type": "number", "minimum": 0, "maximum": 1},
                "fraud":  {"type": "number", "minimum": 0, "maximum": 1},
                "policy": {"type": "number", "minimum": 0, "maximum": 1},
            },
        },
        "thresholds": {
            "type": "object",
            "required": ["approve_below", "decline_above"],
            "properties": {
                "approve_below": {"type": "number", "minimum": 0, "maximum": 1},
                "decline_above": {"type": "number", "minimum": 0, "maximum": 1},
            },
        },
    },
}

_SCHEMAS = {
    "credit_rules":     CREDIT_RULES_SCHEMA,
    "fraud_rules":      FRAUD_RULES_SCHEMA,
    "policy_rules":     POLICY_RULES_SCHEMA,
    "synthesis_weights": SYNTHESIS_WEIGHTS_SCHEMA,
}


def validate_yaml(data: dict, rule_type: str) -> None:
    """Validate a loaded YAML dict against its JSON Schema. Raises ValueError on failure."""
    schema = _SCHEMAS.get(rule_type)
    if schema is None:
        return
    try:
        jsonschema.validate(instance=data, schema=schema)
    except jsonschema.ValidationError as exc:
        raise ValueError(
            f"Invalid {rule_type} YAML at {list(exc.absolute_path)}: {exc.message}"
        ) from exc
