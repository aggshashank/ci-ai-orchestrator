# Validation Plan — AI Credit Card Decisioning Orchestrator

**Document ID:** VAL-001  
**Version:** 1.0.0  
**Status:** Draft — Pre-Production  
**Last updated:** 2026-06-07

---

## 1. Validation Scope

This plan covers independent validation of all model components described in `model_inventory.md`, with primary focus on the Tier 1 Risk Decision Agent (MDL-004) and the Tier 2 LLM agents (MDL-001, MDL-002, MDL-003, MDL-005).

Validation is conducted in accordance with:
- Federal Reserve SR 11-7 (Guidance on Model Risk Management)
- OCC 2011-12 (Supervisory Guidance on Model Risk Management)
- ECOA / Regulation B (fair lending)
- FCRA (credit decisioning)

---

## 2. Validation Team

| Role | Responsibility |
|---|---|
| Model Validator (independent) | Executes validation tests; must be independent of model development team |
| Credit Risk Lead | Reviews decision logic and threshold calibration |
| Compliance Officer | Reviews ECOA compliance, adverse action codes, disparate impact |
| Data Scientist | Reviews LLM prompt engineering and output quality |
| Technology Risk | Reviews system architecture, security, and operational controls |

---

## 3. Conceptual Soundness

### 3.1 Methodology review
- [ ] Review of deterministic scoring formula (Agent 4 signal weights and thresholds)
- [ ] Review of LLM prompt design for agents 1, 2, 3, 5
- [ ] Assessment of RAG retrieval quality (precision@K, recall@K on policy corpus)
- [ ] Review of fallback behaviours for each agent failure mode
- [ ] Assessment of LLM temperature and format constraints

### 3.2 Documentation review
- [ ] Model card complete and accurate (`model_card.md`)
- [ ] Model inventory complete (`model_inventory.md`)
- [ ] All agent decision logic documented

---

## 4. Data Quality and Input Validation

### 4.1 Input data review
- [ ] Validate input schema against FICO data dictionary
- [ ] Confirm creditScore range enforcement (300–850)
- [ ] Confirm utilization range enforcement (0–100%)
- [ ] Test graceful handling of missing optional fields (delinquencies=null, channel=null)
- [ ] Confirm PII fields (name, annualIncome) are not passed to LLM prompts

### 4.2 Boundary and edge case testing
Using golden dataset v2 (`eval/golden_dataset_v2.json`), specifically:

| Test ID | Scenario |
|---|---|
| GD-007 | creditScore exactly at 580 boundary |
| GD-013 | creditScore at 669 (top of FAIR) |
| GD-014 | creditScore at 670 (GOOD entry) |
| GD-016 | utilization exactly at 80% |
| GD-023 | creditScore at minimum FICO (300) |
| GD-009 | Missing optional fields |
| GD-010 | Zero utilization |

All boundary cases must produce the expected tier classification and recommendation.

---

## 5. Outcome Analysis and Benchmarking

### 5.1 Correctness benchmarks

Run `python eval/runner.py --dataset v2` and verify:

| Agent | Minimum correctness | Minimum format |
|---|---|---|
| credit_agent | 0.80 | 1.00 |
| fraud_agent | 0.75 | 1.00 |
| policy_rag_agent | 0.70 | 1.00 |
| risk_decision_agent | 0.90 | 1.00 |
| explainability_agent | 0.65 | 0.90 |
| **Overall pipeline** | **0.78** | — |

### 5.2 Latency benchmarks
- p95 latency per agent must be within `eval_config.py` ceilings
- End-to-end pipeline p95 latency target: < 90 seconds
- Risk Decision Agent p95 latency target: < 1 second (deterministic, no LLM)

### 5.3 Multi-provider validation
Run `python eval/multi_provider_runner.py --providers ollama,groq,openai` to confirm:
- [ ] All providers achieve minimum correctness thresholds
- [ ] Provider comparison report shows < 5% score variance across providers
- [ ] No provider-specific systematic failures on any tier category (approve/decline/manual_review)

---

## 6. Stability and Robustness Testing

### 6.1 Prompt stability
Run eval framework 5× with the same dataset; verify:
- [ ] Risk Decision Agent produces identical output on all 5 runs (deterministic)
- [ ] LLM agents produce consistent riskLevel/fraudRisk classifications (temperature=0 expected to be stable)
- [ ] No more than 1 adverse action code mismatch across 5 runs for any test case

### 6.2 Fallback behaviour testing
For each LLM agent, simulate failure (disconnect Ollama / invalid API key) and verify:
- [ ] Agent returns the documented fallback JSON structure
- [ ] Fallback routes to MANUAL_REVIEW (not auto-approve or silent drop)
- [ ] Error is logged with correlation_id and no PII
- [ ] Pipeline completes end-to-end

### 6.3 Load and concurrency
- [ ] Simulate 10 concurrent application events
- [ ] Confirm no database constraint violations (unique correlation_id)
- [ ] Confirm lru_cache LLM instances are thread-safe

---

## 7. Fair Lending Analysis

### 7.1 Disparate impact testing
Prior to production deployment, analyse decisions on a representative synthetic dataset:
- [ ] Generate synthetic applications with uniform distributions of protected-class proxies
- [ ] Confirm APPROVE/DECLINE/MANUAL_REVIEW rates do not differ by > 80% rule threshold across demographic groups
- [ ] Document findings in a disparate impact testing report

### 7.2 Adverse action code review
- [ ] Confirm every DECLINE produces at least one ECOA adverse action code
- [ ] Confirm adverse action codes map to a federally approved list
- [ ] Confirm explanations are customer-comprehensible (plain_language_summary readability score ≥ grade 8)

---

## 8. Operational Controls Validation

- [ ] `MANUAL_REVIEW` queue endpoint (`GET /api/v1/review-queue`) returns correct pending items
- [ ] Human decision submission (`POST /api/v1/review/{id}/decision`) persists correctly
- [ ] Audit record in PostgreSQL contains all required fields for regulatory reproduction
- [ ] Correlation IDs propagate end-to-end: Spring Boot → Kafka event → Python agents → audit log
- [ ] `X-Correlation-Id` header is echoed in all API responses

---

## 9. Validation Sign-off

| Validator | Role | Date | Signature |
|---|---|---|---|
| | Independent Model Validator | | |
| | Credit Risk Lead | | |
| | Compliance Officer | | |
| | Technology Risk | | |

**Validation outcome:** ☐ Approved ☐ Approved with conditions ☐ Rejected

**Conditions (if any):**

---

## 10. Re-validation Triggers

Re-validation is required when:
- Any LLM model version is updated (Ollama model pull, Groq/OpenAI model upgrade)
- Decision thresholds in Risk Decision Agent change
- New agent is added to the pipeline
- Policy document corpus changes by > 20%
- Production correctness score drops > 5% vs validation baseline
- Disparate impact analysis flags a potential fair lending concern
