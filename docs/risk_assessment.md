# Risk Assessment — AI Credit Card Decisioning Orchestrator

**Document ID:** RISK-001  
**Version:** 1.0.0  
**Status:** Draft — Pre-Production  
**Last updated:** 2026-06-07

---

## 1. Executive Summary

This document identifies, quantifies, and documents controls for material risks associated with deploying the AI Credit Card Decisioning Orchestrator in a production credit underwriting environment. The assessment follows SR 11-7 guidance and covers model risk, operational risk, fair lending risk, and technology risk.

**Overall risk rating:** MEDIUM-HIGH (pre-production; rated for production deployment readiness)

---

## 2. Risk Register

### Risk 1 — LLM Output Unreliability

| Field | Value |
|---|---|
| **Category** | Model Risk |
| **Severity** | HIGH |
| **Likelihood** | MEDIUM |
| **Inherent risk** | HIGH |

**Description:** LLMs produce probabilistic outputs. Even at `temperature=0.0`, repeated calls on identical inputs may produce different JSON structures or invalid responses due to tokenisation artifacts, model version changes, or inference-server instability.

**Controls:**
- JSON format enforcement (`format="json"` for Ollama; `response_format` for OpenAI/Azure)
- Required field validation in each agent before processing output
- Deterministic fallback to HIGH risk / MANUAL_REVIEW on parse failure
- Agent 4 (Risk Decision) is fully deterministic — LLM cannot auto-approve or auto-decline unilaterally
- Eval framework detects format regression (format_floor = 1.00 for most agents)

**Residual risk:** MEDIUM

---

### Risk 2 — Biased LLM Recommendations

| Field | Value |
|---|---|
| **Category** | Fair Lending Risk / Model Risk |
| **Severity** | HIGH |
| **Likelihood** | MEDIUM |
| **Inherent risk** | HIGH |

**Description:** Pre-trained LLMs may encode societal biases that could manifest as disparate treatment or disparate impact on protected-class applicants. The risk is compounded because the model's "reasoning" in natural language is opaque.

**Controls:**
- LLM is used for risk signal assessment only; hard thresholds are enforced in Agent 4 independently
- Protected characteristics are not provided to any LLM agent
- Prompt engineering explicitly constrains LLM to objective risk signals
- Disparate impact testing required before production (see `validation_plan.md` §7)
- MANUAL_REVIEW routing for borderline cases provides a human safety valve
- ECOA adverse action codes derived deterministically, not by LLM

**Residual risk:** MEDIUM

---

### Risk 3 — Policy RAG Staleness

| Field | Value |
|---|---|
| **Category** | Model Risk |
| **Severity** | MEDIUM |
| **Likelihood** | MEDIUM |
| **Inherent risk** | MEDIUM |

**Description:** The policy RAG agent retrieves rules from the Qdrant vector database. If policy documents are not re-ingested after policy changes, the agent will cite outdated rules and may produce incorrect policy_applicable determinations.

**Controls:**
- Re-ingestion script (`scripts/ingest-policies.sh`) is idempotent and can be run on-demand
- Document version metadata should be added to policy `.txt` files
- Policy document changes must trigger a re-ingestion pipeline task
- Policy RAG fallback routes to MANUAL_REVIEW if no chunks retrieved

**Residual risk:** MEDIUM-LOW (with process controls)

---

### Risk 4 — Third-Party LLM Provider Dependency

| Field | Value |
|---|---|
| **Category** | Operational Risk |
| **Severity** | HIGH |
| **Likelihood** | LOW |
| **Inherent risk** | MEDIUM |

**Description:** Cloud LLM providers (Groq, OpenAI, Azure OpenAI) may experience outages, rate limits, or breaking API changes. An outage would route all decisions to MANUAL_REVIEW, potentially overwhelming the human review queue.

**Controls:**
- LLM_PROVIDER is configurable at runtime — switch from cloud to local Ollama without code changes
- Agent fallbacks ensure the pipeline never fails silently
- Local Ollama is the default provider, providing offline resilience
- Provider health checks on startup; ongoing monitoring via `/health` endpoint

**Residual risk:** LOW (multi-provider design)

---

### Risk 5 — Audit Trail Integrity

| Field | Value |
|---|---|
| **Category** | Operational Risk / Compliance Risk |
| **Severity** | HIGH |
| **Likelihood** | LOW |
| **Inherent risk** | MEDIUM |

**Description:** If PostgreSQL persistence fails (connection timeout, constraint violation), the decision may be rendered but not stored, creating a gap in the required audit trail.

**Controls:**
- DB write failures are logged with full correlation_id and error detail
- Persistence is fire-and-forget (`asyncio.ensure_future`) — pipeline is never blocked by DB failure
- Monitoring alert if `decision_persist failed` log events exceed threshold
- Alembic migrations ensure schema consistency on every startup
- PostgreSQL runs with a named volume for durable storage across restarts

**Gap:** There is currently no compensating transaction or dead-letter queue for failed DB writes. This should be addressed before production.

**Residual risk:** MEDIUM (gap noted)

---

### Risk 6 — PII Exposure in Logs

| Field | Value |
|---|---|
| **Category** | Privacy Risk / Compliance Risk |
| **Severity** | HIGH |
| **Likelihood** | LOW |
| **Inherent risk** | MEDIUM |

**Description:** Applicant `name` and `annualIncome` are present in the event payload. Accidental logging of these fields would create a GDPR / state privacy law exposure.

**Controls:**
- `_scrub_pii` processor in `logging_config.py` redacts known PII field names before JSON serialisation
- Agents do not log application fields directly (linter-enforced)
- PII scan required in weekly monitoring (see `monitoring_plan.md` §7)

**Residual risk:** LOW

---

### Risk 7 — Human Override Gaming

| Field | Value |
|---|---|
| **Category** | Compliance Risk / Fraud Risk |
| **Severity** | MEDIUM |
| **Likelihood** | LOW |
| **Inherent risk** | MEDIUM |

**Description:** The HITL endpoint allows any authenticated user to override a MANUAL_REVIEW decision. Without reviewer identity controls, a compromised or malicious reviewer could systematically approve high-risk applications.

**Controls:**
- `reviewer` and `reviewer_notes` are recorded in the audit trail
- Override rates are monitored (see `monitoring_plan.md` §6)
- Production deployment must add authentication to the reviewer endpoints

**Gap:** The current implementation does not enforce reviewer authentication or role-based access control.

**Residual risk:** MEDIUM (authentication gap must be addressed before production)

---

## 3. Controls Summary

| Control | Status | Owner |
|---|---|---|
| Deterministic Agent 4 as binding decision authority | Implemented | Credit Risk Modelling |
| JSON format enforcement on all LLM agents | Implemented | ML Engineering |
| Agent fallbacks to MANUAL_REVIEW | Implemented | ML Engineering |
| ECOA adverse action codes | Implemented | Compliance |
| PII scrubbing in logs | Implemented | ML Engineering |
| Eval framework with regression detection | Implemented | ML Engineering |
| Multi-provider resilience | Implemented | ML Engineering |
| Disparate impact testing | **Not yet completed** | Credit Risk / Compliance |
| DB write dead-letter queue | **Not yet implemented** | ML Engineering |
| Reviewer authentication | **Not yet implemented** | Security Engineering |
| Policy document versioning | **Not yet implemented** | Credit Policy |

---

## 4. Pre-Production Risk Acceptance Criteria

The following items must be completed before production deployment:

- [ ] Disparate impact analysis completed with acceptable results (< 80% rule)
- [ ] Reviewer API authentication implemented
- [ ] DB persistence dead-letter queue or retry mechanism implemented
- [ ] Validation plan executed and signed off (`validation_plan.md`)
- [ ] Policy document versioning process established
- [ ] Production `LLM_PROVIDER` and failover provider agreed
- [ ] Oncall runbook completed for P1 incidents

---

## 5. Residual Risk Summary

| Risk | Inherent | Residual |
|---|---|---|
| LLM output unreliability | HIGH | MEDIUM |
| Biased LLM recommendations | HIGH | MEDIUM |
| Policy RAG staleness | MEDIUM | MEDIUM-LOW |
| Third-party LLM provider outage | MEDIUM | LOW |
| Audit trail integrity | MEDIUM | MEDIUM |
| PII exposure in logs | MEDIUM | LOW |
| Human override gaming | MEDIUM | MEDIUM |
| **Overall** | **HIGH** | **MEDIUM** |

**Recommendation:** Proceed to production only after completing the three pre-production gaps identified above (disparate impact analysis, reviewer authentication, DB persistence resilience).
