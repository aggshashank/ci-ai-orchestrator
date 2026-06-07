# Monitoring Plan — AI Credit Card Decisioning Orchestrator

**Document ID:** MON-001  
**Version:** 1.0.0  
**Status:** Draft — Pre-Production  
**Last updated:** 2026-06-07

---

## 1. Monitoring Objectives

Per SR 11-7, ongoing monitoring must:
1. Detect performance degradation before it materially impacts credit decisions
2. Identify data drift that may render the model stale
3. Ensure operational health (latency, availability, error rates)
4. Provide an audit trail for regulatory examination

---

## 2. Metrics Dashboard

All metrics are exposed via Prometheus and visualised in Grafana (port 3000).

### 2.1 Operational metrics (real-time)

| Metric | Source | Alert threshold |
|---|---|---|
| `agent_execution_seconds` (p95 per agent) | Prometheus Histogram | > latency ceiling from eval_config.py |
| `recommendation_total` (by label) | Prometheus Counter | — |
| `llm_token_usage_total` (by agent) | Prometheus Counter | > 2× expected tokens |
| `manual_review_pending` | Prometheus Gauge | > 50 pending (SLA breach) |
| HTTP error rate `/api/v1/*` | uvicorn access log | > 1% 5xx in 5-min window |
| Kafka consumer lag | kafka-ui / JMX | > 1000 messages |

### 2.2 Model performance metrics (daily / per eval run)

Stored in `eval_runs` PostgreSQL table and optionally pushed to Prometheus:

| Metric | Frequency | Alert threshold |
|---|---|---|
| Pipeline correctness score | Per eval run | < 0.73 (5% regression from 0.78 baseline) |
| credit_agent correctness | Per eval run | < 0.75 |
| risk_decision_agent correctness | Per eval run | < 0.85 |
| APPROVE rate | Daily | Δ > 10% from 30-day rolling average |
| DECLINE rate | Daily | Δ > 10% from 30-day rolling average |
| MANUAL_REVIEW rate | Daily | Δ > 15% from 30-day rolling average |

### 2.3 Data drift metrics (weekly)

| Signal | Method | Alert threshold |
|---|---|---|
| creditScore distribution | Population Stability Index (PSI) | PSI > 0.25 |
| utilization distribution | PSI | PSI > 0.25 |
| delinquencies distribution | PSI | PSI > 0.20 |
| addressMismatch rate | % change | Δ > 20% week-over-week |

---

## 3. Automated Eval Schedule

The eval framework should run as a scheduled job:

```
Frequency:      Daily (off-peak hours, e.g. 02:00 UTC)
Command:        python eval/runner.py --dataset v2 --save-db --provider <active_provider>
Success exit:   0 (no regressions)
Failure action: Alert oncall; block deployment pipeline until reviewed
```

Multi-provider comparison should run weekly:
```
Command:        python eval/multi_provider_runner.py --providers ollama,groq,openai --save-db
```

---

## 4. Alerting and Escalation

### Severity P1 — Immediate action (< 1 hour)
- Pipeline correctness score drops below 0.65
- Risk Decision Agent error rate > 5%
- All LLM agents returning fallback simultaneously
- Database connection failures preventing audit record persistence

**Response:** Page oncall; halt processing; investigate root cause; escalate to Model Risk Management

### Severity P2 — Same business day
- Any single agent correctness regression > 5% vs baseline
- MANUAL_REVIEW queue > 100 pending items
- LLM token usage > 2× expected (cost anomaly)
- Kafka consumer lag > 5000 messages

**Response:** Oncall investigates; no halt unless P1 criteria met

### Severity P3 — Next business day
- Any eval run flagging regressions (even below 5% drop)
- Data drift PSI > 0.15 (warning before alert threshold)
- Single agent latency breach > 1.5× ceiling

**Response:** Engineering team review; document in model monitoring log

---

## 5. Model Performance Log

Every eval run result is stored in the `eval_runs` table with:
- `run_id`, `provider`, `dataset_ver`, `run_at`
- `pipeline_score`, `passed_cases`, `total_cases`
- `regression_count`, `agent_scores` (JSONB), `dimension_scores` (JSONB)

Monthly model performance reports must be produced for Model Risk Management review, showing trend lines for each metric and flagging any drift.

---

## 6. Human-in-the-Loop (HITL) Monitoring

Track the MANUAL_REVIEW queue via:

| Metric | Target | Alert |
|---|---|---|
| Queue length (`manual_review_pending`) | < 20 pending | > 50 |
| SLA: decision within 24 hours | 95% of items | < 90% |
| Human override rate (APPROVE after DECLINE) | < 5% | > 10% |
| Human override rate (DECLINE after APPROVE) | < 2% | > 5% |

High human override rates indicate model miscalibration and trigger re-validation.

---

## 7. Audit and Compliance Monitoring

- **Audit completeness:** All decisions must have a persisted `decisions` record. Monitor for any `explanation` events that fail to write to PostgreSQL.
- **Adverse action codes:** Monthly sampling review by Compliance to confirm codes are accurate and explanations are ECOA-compliant.
- **PII in logs:** Weekly scan of log output to confirm no PII fields (name, annualIncome, SSN) appear in log lines.
- **Correlation ID propagation:** Spot-check 5% of decisions monthly to confirm correlation IDs are consistent across Kafka, PostgreSQL, and log output.

---

## 8. LLM Provider Health

| Check | Frequency | Method |
|---|---|---|
| Ollama health (`GET /api/tags`) | Every 15s | `GET /health` endpoint |
| Model availability (llama3:latest pulled) | On startup | startup health check |
| API key validity (Groq/OpenAI) | Daily | Dry-run eval call |
| Token quota (Groq/OpenAI) | Daily | Provider dashboard / API |
