# Model Inventory — AI Credit Card Decisioning Platform

**Maintained by:** Credit Technology — AI/ML Engineering  
**Review cycle:** Quarterly  
**Last updated:** 2026-06-07

---

## Inventory Purpose

This document enumerates every model component used in the credit card decisioning platform per SR 11-7 requirements. Each component is classified by governance tier, which determines validation depth and ongoing monitoring obligations.

---

## Component Register

### Component 1 — Credit Risk Agent (LLM)

| Field | Value |
|---|---|
| **ID** | MDL-001 |
| **Type** | Large Language Model (prompt-engineered) |
| **Role** | Assess credit risk from bureau signals |
| **Inputs** | creditScore, utilization, delinquencies |
| **Outputs** | riskLevel (HIGH/MEDIUM/LOW), score (0–1), reason, keyFactors |
| **Default LLM** | llama3:latest via Ollama (configurable) |
| **Governance tier** | Tier 2 — inputs to a Tier 1 decision |
| **Fallback** | Returns HIGH risk on any failure |
| **Owner** | Credit Risk Modelling |

### Component 2 — Fraud Risk Agent (LLM)

| Field | Value |
|---|---|
| **ID** | MDL-002 |
| **Type** | Large Language Model (prompt-engineered) |
| **Role** | Evaluate fraud indicators |
| **Inputs** | addressMismatch, delinquencies, channel |
| **Outputs** | fraudRisk (HIGH/MEDIUM/LOW), indicators, recommendAction |
| **Default LLM** | llama3:latest via Ollama (configurable) |
| **Governance tier** | Tier 2 |
| **Fallback** | Returns MEDIUM risk + MANUAL_REVIEW on failure |
| **Owner** | Fraud Prevention |

### Component 3 — Policy RAG Agent (LLM + Vector Search)

| Field | Value |
|---|---|
| **ID** | MDL-003 |
| **Type** | Retrieval-Augmented Generation |
| **Role** | Match application signals against underwriting policy |
| **Sub-components** | nomic-embed-text (embeddings), llama3:latest (LLM), Qdrant (vector DB) |
| **Inputs** | creditScore, utilization, addressMismatch, delinquencies; policy chunks from Qdrant |
| **Outputs** | policy_applicable, rules[], action, citations[] |
| **Governance tier** | Tier 2 |
| **Fallback** | Returns policy_applicable=false + MANUAL_REVIEW on failure |
| **Owner** | Credit Policy & Compliance |

### Component 4 — Risk Decision Agent (Deterministic)

| Field | Value |
|---|---|
| **ID** | MDL-004 |
| **Type** | Rule-based weighted scoring |
| **Role** | Synthesise agent signals into binding recommendation |
| **Inputs** | credit_result, fraud_result, policy_context |
| **Signal weights** | Credit 45%, Fraud 30%, Policy 25% |
| **Outputs** | recommendation (APPROVE/DECLINE/MANUAL_REVIEW), confidence, composite_score |
| **Governance tier** | Tier 1 — binding credit decision |
| **LLM dependency** | None — fully deterministic |
| **Owner** | Credit Risk Modelling |

**Decision thresholds (hard-coded):**
| composite_score | recommendation |
|---|---|
| ≤ 0.35 | APPROVE |
| 0.35 – 0.65 | MANUAL_REVIEW |
| > 0.65 | DECLINE |

### Component 5 — Explainability Agent (LLM)

| Field | Value |
|---|---|
| **ID** | MDL-005 |
| **Type** | Large Language Model (prompt-engineered) |
| **Role** | Generate ECOA-compliant explanation for the decision |
| **Inputs** | recommendation, confidence, credit/fraud/policy signals |
| **Outputs** | plain_language_summary, audit_narrative, recommended_next_steps, adverse_action_codes[] |
| **Governance tier** | Tier 2 |
| **Fallback** | Generic explanation text on failure; adverse action codes still derived deterministically |
| **Owner** | Compliance |

---

## Supporting Infrastructure Models

### Embedding Model — nomic-embed-text

| Field | Value |
|---|---|
| **ID** | MDL-006 |
| **Type** | Sentence embedding model |
| **Role** | Encode policy documents and queries for RAG retrieval |
| **Dimensions** | 768 |
| **Provider** | Ollama (local) |
| **Governance tier** | Tier 3 — supporting infrastructure |

---

## Governance Tier Definitions

| Tier | Description | Validation requirement | Monitoring frequency |
|---|---|---|---|
| **Tier 1** | Directly produces binding credit decisions | Full SR 11-7 validation, backtesting, disparate impact analysis | Monthly |
| **Tier 2** | Produces inputs consumed by a Tier 1 model | Functional validation, correctness benchmarks, prompt stability testing | Quarterly |
| **Tier 3** | Supporting infrastructure (embeddings, infrastructure models) | Functional testing, version pinning | Semi-annual |

---

## LLM Provider Dependencies

| Provider | ID | Notes |
|---|---|---|
| Ollama (local) | llama3:latest | Default for development; no API cost |
| Groq | llama3-8b-8192 | Cloud API; fast inference |
| OpenAI | gpt-4o-mini | Cloud API; highest accuracy in eval |
| Azure OpenAI | Deployment-configured | Enterprise cloud; preferred for production |

---

## Retirement and Change Management

Any change to a Tier 1 or Tier 2 model component requires:
1. Updated validation results in `validation_plan.md`
2. Eval framework regression check (no regression > 5%)
3. Model Risk Management approval
4. Documented version bump in this inventory

Third-party LLM model version changes (e.g. Ollama model update) constitute a **material model change** requiring re-validation.
