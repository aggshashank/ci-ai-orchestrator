# Architecture

## System Overview

```
┌──────────────────────────────────────────────────────────────────────────┐
│                          AI Decisioning Platform                          │
├──────────────────┬───────────────────────────┬──────────────────────────┤
│  Decision API    │     AI Orchestrator        │      Dashboard            │
│  (Spring Boot)   │     (FastAPI)              │      (React + Vite)       │
│  :8080           │     :8001                  │      :3000                │
└────────┬─────────┴─────────────┬─────────────┴──────────────────────────┘
         │ Kafka                 │
         ▼                       │
   ┌─────────────┐               │
   │ application │               ▼
   │ .received   │   ┌──────────────────────────────┐
   └──────┬──────┘   │   LangGraph Agent Pipeline   │
          │          │                              │
          └─────────►│  credit_agent (async)        │
                     │  fraud_agent  (async)        │
                     │  policy_rag_agent (async)    │
                     │  risk_decision_agent (async) │
                     │  explainability_agent (async)│
                     └──────────┬───────────────────┘
                                │
              ┌─────────────────┼─────────────────┐
              ▼                 ▼                 ▼
         ┌─────────┐    ┌──────────────┐   ┌──────────┐
         │ Qdrant  │    │  PostgreSQL  │   │  Kafka   │
         │ vectors │    │  (decisions, │   │ (topics) │
         └─────────┘    │   audit,     │   └──────────┘
                        │   outcomes,  │
                        │   fairness)  │
                        └──────────────┘
```

## Workflows

Four decisioning workflows share the same agent pipeline and strategy framework:

| Workflow | Kafka Topic | Key Agents Used |
|---|---|---|
| **Origination** | `application.received` | credit, fraud, policy RAG, risk decision, explainability |
| **Delinquency** | `delinquency.review.requested` | treatment agent (DPD-floor rules) |
| **Limit Review** | `limit.review.requested` | limit review agent |
| **Cross-Sell** | `cross.sell.evaluation.requested` | propensity agent |

## Agent Pipeline

All agents are `async def` functions in a LangGraph `StateGraph`. The graph is invoked via `graph.ainvoke(state)` which dispatches nodes concurrently when no edges exist between them.

Each agent:
1. Reads its inputs from `GraphState` (a shared TypedDict)
2. Calls `cached_llm_invoke(prompt)` via `asyncio.to_thread` (non-blocking)
3. Returns a `dict` that is merged into `GraphState`

The `explainability_agent` runs last and writes the full audit record to PostgreSQL.

## Strategy Versioning

Decision strategies are versioned YAML directories under `ai-orchestrator/strategies/`:

```
strategies/
  v1.0.0/
    credit_rules.yaml       # thresholds, actions, ECOA codes
    fraud_rules.yaml
    policy_rules.yaml
    synthesis_weights.yaml  # credit/fraud/policy weights
    metadata.yaml
  v1.1.0/
    ...
```

The `StrategyRegistry` table tracks which version is `champion` and which is `challenger`. Champion/challenger traffic splitting is configurable via `CHALLENGER_TRAFFIC_PCT`.

## Champion/Challenger A/B

Traffic routing happens in `messaging/consumer.py`:

```python
if random.random() < settings.challenger_traffic_pct / 100:
    version = challenger_version
else:
    version = champion_version
```

Experiment statistics are collected in PostgreSQL and surfaced via `GET /api/v1/experiments`.

## Adaptive Learning Loop

```
decisions table ──► outcome_consumer (Kafka) ──► decision_outcomes table
                                                          │
                                                    feature_store.py
                                                    (compute signal accuracy)
                                                          │
                                                    model_trainer.py
                                                    (update synthesis_weights.yaml)
                                                          │
                                               get_rules_engine.cache_clear()
                                               (pick up new weights live)
```

MLflow logs each retraining run with metrics and the updated weights file as an artifact.

## Fairness Monitoring

`governance/disparate_impact.py` segments decisions by `channel` and `credit_tier` (proxy variables — ECOA/Reg B prohibits storing protected class data directly). For each segment, it computes:

- `approval_rate` = approvals / total_decisions
- `ratio_to_best` = segment_rate / max(all_segment_rates)
- `violation` = ratio_to_best < 0.80 (4/5ths rule)

Reports are stored as HTML in the `fairness_reports` table and served at `GET /api/v1/governance/fairness/latest/report`.

## Caching and Performance

| Layer | Implementation | Benefit |
|---|---|---|
| LLM responses | SHA-256 keyed dict, TTL 1h, max 256 entries | Eliminates redundant Ollama calls for identical prompts |
| Qdrant client | `@lru_cache()` singleton | One connection pool per process |
| Rules engine | `@lru_cache(maxsize=8)` | YAML loaded once; cleared on strategy change |
| DB sessions | `async_sessionmaker`, `AsyncSession` | Non-blocking I/O throughout |
