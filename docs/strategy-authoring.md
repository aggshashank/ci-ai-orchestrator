# Strategy Authoring Guide

A **strategy** is a versioned directory of YAML files that defines all thresholds, weights, and rules the decisioning engine uses. Changing a strategy requires no code changes — only YAML edits and a new version deploy.

## Directory structure

```
strategies/
  v1.0.0/
    metadata.yaml
    credit_rules.yaml
    fraud_rules.yaml
    policy_rules.yaml
    synthesis_weights.yaml
```

## `metadata.yaml`

```yaml
version: v1.0.0
effective_date: "2026-01-01"
description: "Initial production strategy"
champion: true
changelog:
  - "Initial release"
```

## `credit_rules.yaml`

Defines auto-decisioning thresholds and fallback logic for the credit agent.

```yaml
thresholds:
  auto_decline_score:     580    # scores below this → auto-decline
  auto_approve_score:     750    # scores above this AND utilization below auto_approve_util → auto-approve
  auto_approve_util:      30     # % utilization cap for auto-approve
  high_util_threshold:    80     # above this triggers HIGH utilization flag
  delinquency_high:       3      # >= this many delinquencies → HIGH credit risk

rules:
  - id: AA01
    name: auto_decline_low_score
    condition: "credit_score < thresholds.auto_decline_score"
    action: DECLINE
    ecoa_codes: [AA01]

  - id: AA02
    name: auto_approve_excellent
    condition: "credit_score >= thresholds.auto_approve_score AND utilization < thresholds.auto_approve_util"
    action: APPROVE
    ecoa_codes: []
```

Conditions are evaluated by the rules engine's `_safe_eval()` — only arithmetic comparison operators and `and/or` are permitted. No function calls or imports.

## `fraud_rules.yaml`

```yaml
thresholds:
  high_velocity_threshold: 5    # transactions in 24h
  high_amount_threshold: 10000  # single transaction USD

rules:
  - id: AA07
    name: address_mismatch_high_value
    condition: "address_mismatch AND annual_income > 100000"
    action: MANUAL_REVIEW
    ecoa_codes: [AA07]
```

## `policy_rules.yaml`

Rules evaluated after RAG retrieval. Supplement (not replace) the retrieved policy chunks.

```yaml
rules:
  - id: AA09
    name: combined_risk_policy
    condition: "credit_risk == 'HIGH' AND fraud_risk == 'HIGH'"
    action: DECLINE
    ecoa_codes: [AA09]

  - id: AA12
    name: policy_threshold
    condition: "utilization > 80 AND address_mismatch"
    action: MANUAL_REVIEW
    ecoa_codes: [AA12]
```

## `synthesis_weights.yaml`

Weights used by the `risk_decision_agent` to combine signal scores. Must sum to 1.0.

```yaml
credit_weight: 0.45
fraud_weight:  0.30
policy_weight: 0.25
```

The adaptive learning module (`learning/model_trainer.py`) can automatically update `credit_weight` and `fraud_weight` based on signal accuracy, keeping `policy_weight` fixed at 0.25.

## Authoring workflow

1. Copy an existing version: `POST /api/v1/strategies/deploy`
2. Edit rules in the Rule Editor UI at `/rules` in the dashboard
3. Click **Preview Impact** to run the edited version against golden datasets
4. If the approval rate and confidence metrics look correct, click **Deploy → Activate as Champion**

Or from the CLI:
```bash
# Create new version
curl -X POST http://localhost:8001/api/v1/strategies/deploy \
  -H 'Content-Type: application/json' \
  -d '{"source_version":"v1.0.0","new_version":"v1.1.0","changelog":["Raised score floor"]}'

# Activate
curl -X PUT http://localhost:8001/api/v1/strategies/v1.1.0/activate
```

## Safe eval security model

Rule conditions are evaluated with a restricted `eval()` that permits:
- Comparison operators: `<`, `>`, `<=`, `>=`, `==`, `!=`
- Boolean operators: `and`, `or`, `not`
- Numeric literals
- Variable references to the application context dict

The evaluator rejects any use of `__import__`, `exec`, `eval`, `open`, or attribute access (`__`). Test the security boundary with the provided pytest suite:

```bash
pytest tests/test_origination_workflow.py::TestSafeEval -v
```
