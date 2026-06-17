# API Reference

Base URL: `http://localhost:8001`

All endpoints return JSON unless otherwise noted. Authentication is not required in the default configuration — add a reverse proxy or API gateway for production.

---

## Health

### `GET /health`
Returns service health including Ollama model status and Kafka connectivity.

---

## Decisions

### `GET /api/v1/review-queue`
Returns all decisions pending human review (`recommendation = MANUAL_REVIEW` and no underwriter decision yet).

### `GET /api/v1/audit/{correlationId}`
Returns the full agent trace for a decision: credit result, fraud result, policy context, risk decision, explanation, and ECOA codes.

### `POST /api/v1/review/{correlationId}/decision`
Submit an underwriter decision for a MANUAL_REVIEW case.

```json
{ "decision": "APPROVE", "reviewer": "uw-01", "notes": "Address verified via ID" }
```

---

## Strategies

### `GET /api/v1/strategies`
List all registered strategy versions with status (`champion`, `challenger`, `archived`).

### `GET /api/v1/strategies/{version}`
Get the full snapshot of a strategy version.

### `GET /api/v1/strategies/diff?from=v1.0.0&to=v1.1.0`
Diff two strategy versions. Returns changed thresholds, weight changes, added/removed rules.

### `GET /api/v1/strategies/{version}/rules`
Get the parsed YAML content of all rule files for a version.

### `PUT /api/v1/strategies/{version}/rules`
Update a rule file in-place (clears rules engine cache).

```json
{ "rule_file": "credit_rules", "content": { ... } }
```

### `POST /api/v1/strategies/deploy`
Create a new versioned strategy directory copied from a source version.

```json
{ "source_version": "v1.0.0", "new_version": "v1.1.0", "changelog": ["Raised score floor to 600"] }
```

### `PUT /api/v1/strategies/{version}/activate`
Promote a version to champion.

---

## Simulations

### `POST /api/v1/simulations`
Enqueue a simulation run.

```json
{
  "workflow_type": "ORIGINATION",
  "strategy_version": "v1.1.0",
  "dataset_name": "golden_origination",
  "num_cases": 100
}
```

Returns `{ simulation_id, status: "PENDING" }`.

### `GET /api/v1/simulations/{id}`
Poll simulation status. `status` is `PENDING | RUNNING | COMPLETED | FAILED`.

### `GET /api/v1/simulations/{id}/report`
Returns the HTML simulation report. `Content-Type: text/html`.

---

## Experiments

### `GET /api/v1/experiments`
Returns champion vs. challenger A/B statistics: approval rates, default counts, avg confidence, lift.

---

## Customers

### `GET /api/v1/customers/{customerId}/profile`
Returns enriched customer context including risk tier, tenure, product portfolio, and payment history.

Query param `?refresh=true` forces a cache invalidation.

---

## Governance — Fairness

### `GET /api/v1/governance/fairness/latest`
Returns the most recent fairness analysis result with all segment data.

### `POST /api/v1/governance/fairness/run`
Trigger a new fairness analysis.

```json
{ "period_days": 30 }
```

### `GET /api/v1/governance/fairness/latest/report`
Returns the self-contained HTML fairness report. `Content-Type: text/html`.

---

## Governance — Drift & Retraining

### `GET /api/v1/governance/drift?window_days=30`
Returns the rolling default rate on APPROVE decisions for the specified window.

### `POST /api/v1/governance/retrain?window_days=180&dry_run=false`
Trigger adaptive weight retraining. Set `dry_run=true` to preview new weights without writing.

---

## Analytics

### `GET /api/v1/analytics/trends?days=30`
Returns daily approval rates, rolling default rates, and volume by decision type.

### `GET /api/v1/analytics/segments?days=30`
Returns approval rates broken down by channel and credit tier.

### `GET /api/v1/analytics/strategy-performance?days=90`
Returns per-strategy-version approval rates, average confidence, and confidence distribution.

### `GET /api/v1/analytics/revenue-impact?from=v1.0.0&to=v1.1.0`
Estimates the revenue impact of switching from one strategy version to another.
