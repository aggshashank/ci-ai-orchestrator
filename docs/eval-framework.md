# Eval Framework

The eval framework validates that a strategy version produces the correct decisions across a curated set of golden test cases before promotion to production.

## Golden datasets

Located at `ai-orchestrator/tests/golden_datasets/`:

```
golden_datasets/
  golden_origination.json
  golden_delinquency.json
  golden_limit_review.json
  golden_cross_sell.json
```

Each file is a JSON array of test cases:

```json
[
  {
    "id": "TC-001",
    "description": "Low score below auto-decline threshold",
    "input": {
      "creditScore": 520,
      "utilization": 45.0,
      "delinquencies": 2,
      "annualIncome": 45000,
      "channel": "WEB"
    },
    "expected": {
      "recommendation": "DECLINE",
      "ecoa_codes": ["AA01"]
    }
  }
]
```

## Running evals

### Via pytest (CI)

```bash
cd ai-orchestrator
pytest tests/ -v -k "golden"
```

### Via API

```bash
curl -X POST http://localhost:8001/api/v1/simulations \
  -H 'Content-Type: application/json' \
  -d '{
    "workflow_type": "ORIGINATION",
    "strategy_version": "v1.1.0",
    "dataset_name": "golden_origination",
    "num_cases": 50
  }'
```

Poll `GET /api/v1/simulations/{id}` until `status == COMPLETED`, then fetch the HTML report via `GET /api/v1/simulations/{id}/report`.

### Via dashboard

Navigate to **Evals** → enter a strategy version → click **Run All Evals**.

## Regression gate

The `strategy/manager.py` enforces a regression gate on strategy deployment:
- Approval rate must not drop more than 5 percentage points vs. the champion
- ECOA code coverage must remain at 100% (every DECLINE must have at least one code)

If the gate fails, the deployment is rejected with a `422` response.

## Adding test cases

1. Open the relevant golden dataset JSON file
2. Add a new entry with a unique `id`, descriptive `description`, `input`, and `expected`
3. Run `pytest tests/ -v` to verify the new case passes
4. Submit a PR

For security rule tests (safe-eval boundary), add cases to `tests/test_origination_workflow.py::TestSafeEval`.

## MLflow tracking

Each simulation run is logged to MLflow with:
- `strategy_version`, `workflow_type`, `dataset_name`
- `approval_rate`, `avg_confidence`, `error_count`
- The full metrics dict as a JSON artifact

View runs at `http://localhost:5000` (default MLflow UI).
