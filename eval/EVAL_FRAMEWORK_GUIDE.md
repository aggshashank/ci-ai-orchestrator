# Agent Evaluation Framework — Complete Guide

> **Purpose:** Automated, repeatable scoring of all five AI agents across four dimensions: correctness, format, latency, and cost.  
> **When to run:** Before every prompt change, model swap, dependency upgrade, and policy document update.

---

## Table of Contents

1. [Framework Overview](#1-framework-overview)
2. [Project Structure](#2-project-structure)
3. [Setup](#3-setup)
4. [The Golden Dataset](#4-the-golden-dataset)
5. [Dimension Scorers](#5-dimension-scorers)
6. [Running the Eval](#6-running-the-eval)
7. [Reading the Report](#7-reading-the-report)
8. [Managing Baselines and Regressions](#8-managing-baselines-and-regressions)
9. [Tuning Thresholds](#9-tuning-thresholds)
10. [Extending the Framework](#10-extending-the-framework)
11. [CI Integration](#11-ci-integration)
12. [Interview Talking Points](#12-interview-talking-points)

---

## 1. Framework Overview

### What it does

For each test case in the golden dataset, the framework:

1. Builds a `GraphState` from the application fixture
2. Invokes each agent in pipeline order (so downstream agents receive upstream outputs)
3. Scores four dimensions per agent: correctness, format, latency, cost
4. Aggregates into a weighted agent score, then a weighted pipeline score
5. Compares against a saved baseline and flags score drops above the regression threshold
6. Writes a JSON result and an HTML report

### Architecture

```
golden_dataset.json
        │
        ▼
   runner.py  ──────────────────────────────────────────────┐
        │                                                    │
        ├─► credit_agent        ─► scorers ─► AgentResult   │
        ├─► fraud_agent         ─► scorers ─► AgentResult   │
        ├─► policy_rag_agent    ─► scorers ─► AgentResult   │
        ├─► risk_decision_agent ─► scorers ─► AgentResult   │
        └─► explainability_agent─► scorers ─► AgentResult   │
                                                    │        │
                                             aggregator.py   │
                                                    │        │
                                    ┌───────────────▼────────▼───┐
                                    │   PipelineEvalResult        │
                                    │   pipeline_score            │
                                    │   agent_scores              │
                                    │   regressions               │
                                    └──────────┬─────────────────┘
                                               │
                                    ┌──────────▼─────────────────┐
                                    │   report_generator.py       │
                                    │   reports/latest.html       │
                                    └────────────────────────────┘
```

### Scoring formula

```
agent_weighted_score = (
    correctness × 0.50 +
    format      × 0.25 +
    latency     × 0.15 +
    cost        × 0.10
)

pipeline_score = weighted_average(agent_scores, weights=AGENT_THRESHOLDS.weight)
```

The risk decision agent has `weight=1.5` (50% more important than others) because it produces the final recommendation.

---

## 2. Project Structure

```
eval/
├── golden_dataset.json          # 10 labelled test cases (extend to 50+)
├── eval_config.py               # ALL thresholds and weights — edit here
├── runner.py                    # main entry point
├── aggregator.py                # score combination + baseline comparison
├── report_generator.py          # HTML report builder
├── scorers/
│   ├── __init__.py
│   ├── format_scorer.py         # JSON schema validation
│   ├── correctness_scorer.py    # exact match + LLM-as-judge
│   ├── latency_scorer.py        # wall-clock time scoring
│   └── cost_scorer.py           # token counting + cost projection
├── baselines/
│   └── baseline.json            # saved reference run (auto-generated)
├── reports/
│   └── latest.html              # latest eval report (auto-generated)
└── EVAL_FRAMEWORK_GUIDE.md      # this file
```

---

## 3. Setup

### 3.1 Dependencies

The eval framework reuses the `ai-orchestrator` virtualenv. No additional packages needed beyond:

```bash
cd ai-orchestrator
source venv/Scripts/activate   # Git Bash on Windows

# Verify these are already installed (from requirements.txt)
python -c "import json, time, argparse; print('stdlib ok')"
python -c "import httpx; print('httpx ok')"
```

The framework imports `httpx` for LLM-as-judge calls. It is already in `requirements.txt`.

### 3.2 Verify services are running

The eval runner invokes real agents, which need:

```bash
# 1. Ollama running
curl http://localhost:11434/api/tags

# 2. Qdrant running (needed by policy_rag_agent)
curl http://localhost:6333/health

# 3. Policy documents ingested
cd ai-orchestrator && python ingest_policies.py
```

### 3.3 Dry run (validates setup without LLM calls)

```bash
cd eval
python runner.py --dry-run
```

Expected output:

```
============================================================
  Eval Run: eval-20260523-010203-a1b2c3d4
  Cases:    10
  Agents:   credit_agent, fraud_agent, policy_rag_agent, risk_decision_agent, explainability_agent
  Mode:     DRY RUN
============================================================

  [GD-001] clear_approve_excellent_profile
    ✓ credit_agent             corr=0.50 fmt=1.00 lat=0.0s  weighted=0.65
    ...
```

---

## 4. The Golden Dataset

### 4.1 Structure

Each entry in `golden_dataset.json`:

```json
{
  "id": "GD-001",
  "scenario": "clear_approve_excellent_profile",
  "description": "Human-readable reason this case was included",
  "tier": "approve",
  "application": {
    "name": "Alice Chen",
    "creditScore": 790,
    "utilization": 18.0,
    "addressMismatch": false,
    "delinquencies": 0,
    "channel": "WEB"
  },
  "expected": {
    "credit_agent":   { "riskLevel": "LOW", "score_max": 0.25 },
    "fraud_agent":    { "fraudRisk": "LOW", "recommendAction": "PROCEED" },
    "policy_rag_agent": { "action": "APPROVE", "policy_applicable": false },
    "risk_decision":  { "recommendation": "APPROVE", "confidence_min": 0.65 },
    "explainability": {
      "adverse_action_codes_expected": [],
      "summary_must_not_contain": ["decline", "manual review"]
    }
  }
}
```

### 4.2 Tiers to cover

Always have test cases in all three tiers:

| Tier | Cases needed | What to test |
|---|---|---|
| `approve` | 3–5 | Clear approvals, zero utilization, all optionals present/absent |
| `decline` | 3–5 | Score < 580, all signals HIGH, delinquencies >= 3 |
| `manual_review` | 5–8 | Policy thresholds, borderline scores, single fraud signal |

### 4.3 Adversarial cases (important)

Include cases specifically designed to break agents:

```json
{ "creditScore": 580, ... }    // exactly at threshold
{ "creditScore": 800, "utilization": 0.0, ... }  // zero utilization
{ "name": "Test", "creditScore": 740, "utilization": 25.0 }  // no optional fields
```

These catch regressions that only appear at edge values.

### 4.4 Adding a new test case

1. Add the JSON entry to `golden_dataset.json`
2. Assign the next sequential ID (`GD-011`, etc.)
3. Run `python runner.py --case GD-011 --dry-run` to validate the schema
4. Run `python runner.py --case GD-011` to get actual agent outputs
5. Verify the outputs match your expectations
6. If all good, save baseline: `python runner.py --save-baseline`

---

## 5. Dimension Scorers

### 5.1 Format scorer (`scorers/format_scorer.py`)

**What it checks:**
- Output parses as valid JSON (score = 0.0 if not)
- All required keys present (−0.20 per missing key)
- Enum values within allowed set (−0.25 per violation)
- Correct field types (−0.15 per violation)
- No markdown fences or headings contaminating the output (−0.20)

**Example violation — enum out of range:**
```json
{ "riskLevel": "CRITICAL" }   // not in {HIGH, MEDIUM, LOW} → -0.25
```

**Debugging format failures:**
```bash
python runner.py --case GD-002 --agent credit_agent
# Look for format issues in the output
```

### 5.2 Correctness scorer (`scorers/correctness_scorer.py`)

**Exact match checks (deterministic agents):**

| Field | Check | Weight |
|---|---|---|
| `riskLevel` | Exact match vs expected | 1.0 |
| `score` | Within `score_min`/`score_max` bounds | 1.0 |
| `fraudRisk` | Exact match | 1.0 |
| `recommendation` | Exact match (double weight) | 2.0 |
| `confidence` | Above `confidence_min` | 1.0 |
| `adverse_action_codes` | Expected codes all present | 1.0 |

**LLM-as-judge (explainability agent):**

Enable with `--judge` flag. The judge LLM scores the `plain_language_summary` on a 0–3 rubric:

```
0 = Wrong, misleading, or empty
1 = Partially correct, missing key information
2 = Correct and complete
3 = Correct, complete, and clearly written for a customer
```

The judge score is normalized to 0.0–1.0 and contributes 1 point to the correctness calculation.

**Judge prompt (in `correctness_scorer.py`):**

```python
JUDGE_PROMPT = """You are evaluating a credit card application decision explanation.
Score the following explanation on a scale from 0 to 3:
0 = Wrong, misleading, or empty
1 = Partially correct but missing key information
2 = Correct and complete
3 = Correct, complete, and clearly written for a customer

Explanation to evaluate:
"{summary}"

Respond ONLY with a JSON object: {"score": <integer 0-3>, "reason": "<one sentence>"}"""
```

**Customising the rubric:**

Edit `JUDGE_PROMPT` in `correctness_scorer.py`. Add criteria specific to your policy (e.g., "must mention the specific policy threshold that was violated").

### 5.3 Latency scorer (`scorers/latency_scorer.py`)

**Scoring curve:**

```
score = 1.0              if latency <= ceiling
score = 1.0 - overage   if ceiling < latency <= 3× ceiling  (linear decay)
score = 0.0              if latency > 3× ceiling
score = 0.0              if timed_out
score -= 0.30            if fallback_used
```

**Configuring ceilings:**

Edit `latency_ceiling_s` in `eval_config.py` per agent. Current defaults:

| Agent | Ceiling (CPU) | Ceiling (GPU target) |
|---|---|---|
| credit_agent | 120s | 5s |
| fraud_agent | 90s | 5s |
| policy_rag_agent | 180s | 8s |
| risk_decision_agent | 1s | 1s |
| explainability_agent | 120s | 5s |

### 5.4 Cost scorer (`scorers/cost_scorer.py`)

**Token counting:**

Currently uses an approximation (`len(output.split()) * 2`). For production accuracy, extract actual token counts from the Ollama API response:

```python
# In runner.py invoke_agent(), replace the approximation with:
response = ollama_client.generate(model=model, prompt=prompt)
prompt_tokens = response.get("prompt_eval_count", 400)
completion_tokens = response.get("eval_count", 100)
```

**Cost projection:**

The report shows estimated cost per 1000 applications at configured provider pricing. Update `COST_PER_1M_TOKENS` in `eval_config.py` when switching providers.

---

## 6. Running the Eval

### 6.1 Commands

```bash
cd eval
source ../ai-orchestrator/venv/Scripts/activate

# Run all agents, all test cases
python runner.py

# Single agent (fast feedback during prompt development)
python runner.py --agent credit_agent

# Single test case (debugging a specific scenario)
python runner.py --case GD-003

# With LLM-as-judge for explainability scoring
python runner.py --judge

# Save this run as the new baseline
python runner.py --save-baseline

# Generate HTML report
python runner.py --report

# Validate config and dataset without any LLM calls
python runner.py --dry-run

# Full production run: judge + report + save baseline
python runner.py --judge --report --save-baseline
```

### 6.2 Expected runtime

On CPU with Llama 3 8B:

| Scope | Approx time |
|---|---|
| Dry run (10 cases, 5 agents) | ~1 second |
| Single agent, 10 cases | ~8 minutes |
| All agents, 10 cases | ~40 minutes |
| All agents, 50 cases | ~3 hours |

> **Tip:** Run `--agent credit_agent` while developing prompt changes to the credit agent. Run the full suite only before merging.

### 6.3 Console output explained

```
  [GD-003] manual_review_high_utilization_address_mismatch
    ✓ credit_agent             corr=0.85 fmt=1.00 lat=47.3s weighted=0.89
    ✗ fraud_agent              corr=0.50 fmt=1.00 lat=43.1s weighted=0.73
    ✓ policy_rag_agent         corr=1.00 fmt=1.00 lat=124.0s weighted=0.91
    ✓ risk_decision_agent      corr=1.00 fmt=1.00 lat=0.0s  weighted=1.00
    ✓ explainability_agent     corr=0.75 fmt=1.00 lat=68.2s weighted=0.84
```

- `✓` = agent passed all threshold checks for this case
- `✗` = one or more thresholds not met
- `corr` = correctness score (0–1)
- `fmt` = format score (0–1)
- `lat` = latency wall-clock seconds (lower is better)
- `weighted` = weighted combination of all four dimensions

---

## 7. Reading the Report

Open `reports/latest.html` in a browser after running with `--report`.

### Sections

**Overall pipeline score** — single percentage. Target: ≥ 80% for production deployment.

**Dimension scores (pipeline average)** — four metric cards showing averages across all agents and test cases. Look for:
- Format < 100% → JSON schema violations in some agents
- Latency dropping → prompts getting longer, or model slower
- Correctness dropping → prompt regression or model quality issue

**Agent scores table** — per-agent breakdown with colour-coded bars. Red = below threshold.

**Regression analysis** — lists any score drops vs saved baseline, with severity (HIGH = > 15% drop).

**Eval configuration** — the thresholds used in this run (transparency for audits).

---

## 8. Managing Baselines and Regressions

### 8.1 When to save a new baseline

Save a new baseline when:
- All agents pass their thresholds on the full test set
- A deliberate performance trade-off was made and accepted (e.g. switched to a slower but more accurate model)
- New test cases were added to the golden dataset

```bash
python runner.py --save-baseline
```

The baseline is saved to `baselines/baseline.json`. Commit this file to git so the team shares the same reference.

### 8.2 Understanding regression severity

| Severity | Trigger | Action |
|---|---|---|
| HIGH | Score dropped > 15% | Block merge. Investigate immediately. |
| MEDIUM | Score dropped 5–15% | Review the change that caused it. May need prompt fix. |
| None | Score stable or improved | Safe to merge. |

### 8.3 Common regression causes

| Symptom | Likely cause | Fix |
|---|---|---|
| Format drops to < 1.0 | Prompt change added prose before JSON | Re-add "Return ONLY a JSON object" |
| Correctness drops on credit_agent | Utilization threshold changed in prompt | Revert or retune prompt |
| Latency score drops | Prompt got longer, more tokens to generate | Trim prompt |
| All agents regress simultaneously | LangChain/Ollama version upgrade | Pin versions, test before upgrading |

---

## 9. Tuning Thresholds

All thresholds live in `eval_config.py`. Edit and re-run to see impact.

### 9.1 Threshold guide

**Correctness floor** — start at 0.75 for LLM agents, 0.90 for deterministic agents. Raise as the system matures. Never set below 0.60.

**Format floor** — always 1.00. Format failures cause silent pipeline breaks. No exceptions.

**Latency ceiling** — set to your production SLA × 1.5 (buffer for test environment variance). On CPU, current defaults are realistic. With GPU, set to 5–8s.

**Token ceiling** — run 10 test cases, look at actual token counts in Ollama logs, set ceiling at mean + 2× standard deviation.

### 9.2 Dimension weights

Default weights (in `DIMENSION_WEIGHTS`):

```python
DIMENSION_WEIGHTS = {
    "correctness": 0.50,   # most important — did it get the right answer?
    "format":      0.25,   # critical for pipeline stability
    "latency":     0.15,   # important for UX
    "cost":        0.10,   # important for budget
}
```

For a cost-sensitive deployment (e.g. using paid API), increase cost weight to 0.20 and decrease latency to 0.05.

---

## 10. Extending the Framework

### 10.1 Add a new test case (do this regularly)

```bash
# Edit golden_dataset.json — add an entry with the next ID
# Then validate:
python runner.py --case GD-011 --dry-run

# Run it live:
python runner.py --case GD-011

# If outputs match expectations, add to baseline:
python runner.py --save-baseline
```

### 10.2 Add a new agent

1. Add the agent function to `ai-orchestrator/agents/`
2. Add its schema to `AGENT_SCHEMAS` in `scorers/format_scorer.py`
3. Add a scorer function in `scorers/correctness_scorer.py`
4. Add thresholds to `AGENT_THRESHOLDS` in `eval_config.py`
5. Add it to `agent_fns` in `runner.py`
6. Add `expected` entries in golden dataset cases

### 10.3 Add a new eval dimension

Create `scorers/fairness_scorer.py` (example for bias detection):

```python
"""
fairness_scorer.py
Score whether recommendations differ by protected-class-correlated features.
"""
def score_fairness(recommendation: str, application: dict) -> float:
    # Check: does channel=PARTNER correlate with higher DECLINE rate?
    # Implement disparate impact analysis here
    ...
```

Then add to `runner.py` alongside the existing four scorers.

### 10.4 Real token counts from Ollama

Replace the token approximation in `runner.py` with actual counts:

```python
import httpx

def invoke_with_token_counts(prompt: str, model: str) -> tuple[str, int, int]:
    resp = httpx.post("http://localhost:11434/api/generate",
        json={"model": model, "prompt": prompt, "format": "json", "stream": False},
        timeout=180)
    data = resp.json()
    return (
        data["response"],
        data.get("prompt_eval_count", 0),    # actual prompt tokens
        data.get("eval_count", 0),            # actual completion tokens
    )
```

---

## 11. CI Integration

### 11.1 GitHub Actions workflow

Create `.github/workflows/eval.yml`:

```yaml
name: Agent Eval

on:
  pull_request:
    paths:
      - 'ai-orchestrator/agents/**'
      - 'ai-orchestrator/llm_provider.py'
      - 'policy-documents/**'
      - 'eval/**'

jobs:
  eval:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          cd ai-orchestrator
          pip install -r requirements.txt
          pip install -e .

      - name: Start Qdrant
        run: |
          docker run -d --name qdrant -p 6333:6333 qdrant/qdrant:latest
          sleep 5

      - name: Ingest policy documents
        run: |
          cd ai-orchestrator
          python ingest_policies.py
        env:
          QDRANT_URL: http://localhost:6333
          OLLAMA_BASE_URL: http://localhost:11434   # Ollama not available in CI
          POLICY_DOCS_PATH: ../policy-documents

      - name: Run eval (dry run in CI — no LLM)
        run: |
          cd eval
          python runner.py --dry-run --report
        # Note: use --dry-run in CI unless you have a GPU runner with Ollama

      - name: Upload report
        uses: actions/upload-artifact@v4
        with:
          name: eval-report
          path: eval/reports/latest.html
```

> **CI without GPU:** Use `--dry-run` in CI to validate dataset and config integrity without LLM calls. Run the live eval locally before merging and save the baseline. The CI job then catches dataset schema errors and config mistakes.

### 11.2 Exit codes

The runner exits with:
- `0` — eval passed, no regressions
- `1` — regressions detected

This makes it easy to use as a CI gate:

```bash
python runner.py || echo "EVAL FAILED — regressions detected"
```

---

## 12. Interview Talking Points

### "How do you ensure your AI agents maintain quality over time?"

> "We have an automated eval framework that runs against a golden dataset of 10+ labelled test cases on every prompt change, model upgrade, and dependency update. It scores four dimensions per agent: correctness via exact match and LLM-as-judge, format via JSON schema validation, latency via wall-clock time percentiles, and cost via token counting. The aggregated pipeline score is compared against a saved baseline and flags regressions above 5%. In regulated fintech, you need this — a prompt tweak that improves one agent can silently break another, and you only find out when a customer gets the wrong adverse action code."

### "What is LLM-as-judge and when do you use it?"

> "For structured outputs like riskLevel or recommendation, exact match is sufficient and cheap. But for the explainability agent's plain language summary — which has to be correct, complete, and customer-appropriate — you can't match it exactly. LLM-as-judge uses a second LLM call with an explicit rubric (0 = wrong, 3 = correct and clearly written) to score free-text outputs. The key is the rubric specificity. Vague rubrics produce inconsistent judge scores. We use temperature=0 on the judge to make scores deterministic."

### "What's in your golden dataset?"

> "10 cases today, target 50 for production. Each case has an application fixture, expected outputs per agent, keyword constraints on the explanation summary, and expected adverse action codes. We deliberately include edge cases: credit score exactly at the 580 decline threshold, zero utilization, missing optional fields. We also have adversarial cases designed to trigger specific failure modes — like an excellent credit score paired with 98% utilization, which should route to MANUAL_REVIEW not APPROVE even though credit risk is low. Those are the cases that catch regressions."

### "How do you handle the fact that LLMs are non-deterministic?"

> "Three mitigations. First, temperature=0.0 on all agents minimises but doesn't eliminate variance. Second, the eval runner supports running each case N times and taking the median — we flag test cases where variance exceeds a threshold as 'flaky', which is itself actionable signal. Third, we use format=json in Ollama which constrains token sampling to valid JSON tokens and significantly reduces output variation."

---

*AI Credit Card Decisioning POC — Eval Framework*
