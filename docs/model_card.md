# Model Card — AI Credit Card Decisioning Orchestrator

**Version:** 1.0.0 | **Date:** 2026-06-07 | **Status:** Development / Pre-Production

---

## Model Summary

| Field | Value |
|---|---|
| **Model name** | AI Credit Card Decisioning Orchestrator |
| **Model type** | Multi-agent LLM pipeline (LangGraph) |
| **Task** | Credit card application risk assessment and decisioning |
| **Owner** | Credit Technology — AI/ML Engineering |
| **Governance tier** | Tier 1 — High-impact credit decision model |
| **Regulatory framework** | SR 11-7, ECOA, FCRA, Fair Lending |

---

## Intended Use

### Primary use case
Automated risk assessment for credit card applications. The system ingests an application event, evaluates credit risk, fraud risk, and policy compliance in parallel, synthesises a recommendation, and generates a customer-facing explanation.

### Decision outputs
| Output | Meaning |
|---|---|
| `APPROVE` | Application meets all underwriting criteria |
| `DECLINE` | Application fails one or more hard decline criteria |
| `MANUAL_REVIEW` | Signals are ambiguous; a human underwriter must adjudicate |

### Intended users
- Credit underwriting automation pipeline (primary, automated)
- Human underwriters reviewing the `MANUAL_REVIEW` queue (secondary)
- Compliance and audit teams reviewing the decision audit trail

### Out-of-scope uses
- Loan products other than credit cards
- Commercial / business credit applications
- Real-time re-scoring after bureau data refresh
- Any decision that bypasses the `MANUAL_REVIEW` fallback path

---

## Model Architecture

The orchestrator is a **five-agent LangGraph pipeline**. Agents 1–3 run in parallel; agents 4–5 run sequentially after parallel completion.

```
ApplicationReceivedEvent (Kafka)
    │
    ├─── [1] Credit Risk Agent     ← Evaluates credit score, utilization, delinquencies
    ├─── [2] Fraud Risk Agent      ← Evaluates address mismatch, velocity, channel
    └─── [3] Policy RAG Agent      ← Retrieves relevant policy rules from Qdrant
         │
    [4] Risk Decision Agent        ← Deterministic weighted scoring (no LLM)
         │
    [5] Explainability Agent       ← Generates ECOA-compliant explanation
         │
    PostgreSQL decision store      ← Audit record persisted
    Kafka decision.completed       ← Event published
```

### LLM dependency
Agents 1, 2, 3, and 5 call an LLM (configurable: Ollama, Groq, OpenAI, Azure OpenAI). Agent 4 is fully deterministic and does not call an LLM.

The LLM is used for **structured judgment**, not rule execution. Hard decline thresholds (score < 580, utilization > 80%, delinquencies ≥ 3) are enforced in the deterministic Agent 4 layer regardless of LLM output.

---

## Input Features

| Feature | Type | Source | PII? |
|---|---|---|---|
| `creditScore` | Integer (300–850) | Credit bureau | No — aggregated score |
| `utilization` | Float (0–100%) | Credit bureau | No — aggregated metric |
| `delinquencies` | Integer (≥ 0) | Credit bureau | No — count |
| `addressMismatch` | Boolean | Bureau / application | No — binary signal |
| `channel` | String | Application | No |
| `annualIncome` | Float (optional) | Application | Sensitive — not used in LLM prompts |
| `name` | String | Application | PII — never logged, not used in decisioning |

**Note:** `name` and `annualIncome` are present in the event payload for regulatory completeness but are not used as inputs to any agent's LLM prompt.

---

## Performance

Performance benchmarks from the eval framework (`eval/runner.py`):

| Agent | Correctness floor | Format floor | Latency ceiling |
|---|---|---|---|
| Credit Risk | 0.80 | 1.00 | 120 s |
| Fraud Risk | 0.75 | 1.00 | 90 s |
| Policy RAG | 0.70 | 1.00 | 180 s |
| Risk Decision | 0.90 | 1.00 | 1 s |
| Explainability | 0.65 | 0.90 | 120 s |

Target overall pipeline score: **≥ 0.78** (weighted average across all agents).

---

## Fairness and Bias Considerations

### Protected characteristics
The model does not receive, process, or use any of the following protected characteristics defined under ECOA and the Fair Housing Act: race, color, religion, national origin, sex, marital status, age (other than minimum legal age), receipt of public assistance.

### Proxy variable risk
`addressMismatch` and `channel` are behavioural signals that could correlate with protected characteristics. Mitigation:
- These signals are evaluated as fraud indicators, not creditworthiness indicators
- Both signals route to `MANUAL_REVIEW` (not auto-decline) when elevated
- Disparate impact testing must be performed prior to production deployment (see `validation_plan.md`)

### LLM bias risk
LLM-based agents (1, 2, 5) may reflect biases present in pre-training data. Mitigations:
- `temperature=0.0` for deterministic outputs
- `format="json"` / `response_format` constraints to reduce free-form generation
- Agent 4 (deterministic) is the binding decision authority
- Regular eval framework runs detect performance drift

---

## Limitations

1. **LLM reliability:** Agents fall back to conservative defaults (HIGH risk, MANUAL_REVIEW) on LLM failures, which may increase manual review volume.
2. **RAG coverage:** Policy RAG depends on Qdrant collection completeness. Outdated policy documents will produce stale guidance.
3. **Latency:** Ollama local inference can exceed 120 s per agent on constrained hardware, breaching the latency SLA.
4. **Context window:** LLM context limits constrain the number of policy chunks retrievable; complex applications may receive incomplete policy coverage.
5. **Single bureau:** Currently ingests a single application event without multi-bureau reconciliation.

---

## Ethical Considerations

- All credit decisions generate ECOA-compliant adverse action codes (AA01–AA12).
- Human-in-the-loop is mandatory for all `MANUAL_REVIEW` decisions.
- No auto-decline can be overridden by an LLM; only Agent 4 deterministic logic triggers DECLINE.
- Full audit trail is persisted in PostgreSQL with immutable correlation IDs.
- PII (name, income) is redacted from all log output.

---

## Version History

| Version | Date | Changes |
|---|---|---|
| 1.0.0 | 2026-06-07 | Initial development release |
