# Changelog

All notable changes to this project will be documented in this file.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
Versioning follows [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [1.0.0] — 2026-06-17

### Added

**Phase 4 — Platform Experience**
- React 18 + Vite + Tailwind dashboard with 10 pages (Strategy, Rule Editor, Simulation, Experiments, Analytics, Decisions, Fairness, Evals, Rule Preview, Rule Deploy)
- Analytics backend: `aggregator.py`, `trends.py`, `revenue_model.py` with 4 new API endpoints
- Rule editor API endpoints: `GET/PUT /api/v1/strategies/{version}/rules`, `POST /api/v1/strategies/deploy`, `PUT /api/v1/strategies/{version}/activate`
- Apache 2.0 license, contributing guide, this changelog
- CI/CD workflows: lint + test, Docker publish, release

**Phase 3 — Production Hardening**
- Outcome events & adaptive learning (`learning/` package): MLflow-tracked weight retraining, feature store, drift detector
- Fairness monitoring (`governance/` package): 4/5ths rule disparate impact analysis, HTML reports, Slack/email alerts
- All 8 agents converted to fully async (`async def` + `asyncio.to_thread`)
- LLM response cache (SHA-256, TTL 1h, LRU max-256)
- Qdrant connection pool singleton via `@lru_cache`
- Async Kafka consumer with `graph.ainvoke()`
- DB migrations 008 (`decision_outcomes`), 009 (`fairness_reports`)

**Phase 2 — Multi-Workflow Decisioning**
- Four decisioning workflows: Origination, Delinquency, Limit Review, Cross-Sell
- Rules engine with YAML-configurable thresholds and champion/challenger versioning
- A/B experiment framework: traffic splitting, statistical significance testing
- Strategy manager with snapshot, diff, and activation
- Simulation engine for pre-deployment impact analysis
- Customer context service with profile enrichment
- DB migrations 004–007

**Phase 1 — Foundation**
- LangGraph multi-agent pipeline: Credit, Fraud, Policy RAG, Risk Decision, Explainability
- ECOA-compliant adverse action codes (AA01–AA12)
- Event-driven architecture (Kafka + DLQ)
- Human-in-the-loop review queue
- Qdrant vector store with RAG policy retrieval
- Prometheus metrics, structlog structured logging
- DB schema + Alembic migrations 001–003
- Golden datasets and pytest test harness
- Eval framework with HTML reports
- MLflow simulation tracking
- Model card, model inventory, validation plan, risk assessment

[Unreleased]: https://github.com/your-org/ai-decisioning-platform/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/your-org/ai-decisioning-platform/releases/tag/v1.0.0
