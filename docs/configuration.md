# Configuration Reference

All settings are read from environment variables (or a `.env` file in `ai-orchestrator/`).
Pydantic Settings handles parsing, coercion, and defaults.

## Core

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://...` | Async PostgreSQL connection string |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server |
| `OLLAMA_MODEL` | `llama3` | LLM model name |
| `OLLAMA_EMBED_MODEL` | `nomic-embed-text` | Embedding model name |
| `QDRANT_URL` | `http://localhost:6333` | Qdrant vector store |
| `QDRANT_COLLECTION` | `policy_docs` | Collection name |
| `KAFKA_BOOTSTRAP_SERVERS` | `localhost:9092` | Kafka broker(s) |
| `KAFKA_GROUP_ID` | `ai-orchestrator` | Consumer group |

## Kafka Topics

| Variable | Default |
|---|---|
| `KAFKA_TOPIC_APPLICATION_RECEIVED` | `application.received` |
| `KAFKA_TOPIC_RECOMMENDATION_GENERATED` | `recommendation.generated` |
| `KAFKA_TOPIC_MANUAL_REVIEW_REQUIRED` | `manual.review.required` |
| `KAFKA_TOPIC_DLQ` | `application.dlq` |
| `KAFKA_TOPIC_OUTCOME_DEFAULT` | `outcome.account_default` |
| `KAFKA_TOPIC_OUTCOME_FRAUD` | `outcome.fraud_confirmed` |
| `KAFKA_TOPIC_OUTCOME_PAYOFF` | `outcome.early_payoff` |

## Strategy & Experiments

| Variable | Default | Description |
|---|---|---|
| `STRATEGIES_DIR` | `strategies` | Path to strategy YAML directory |
| `ACTIVE_STRATEGY_VERSION` | `v1.0.0` | Champion version |
| `CHALLENGER_VERSION` | `` | Challenger version (empty = off) |
| `CHALLENGER_TRAFFIC_PCT` | `0` | % traffic sent to challenger |

## LLM Cache

| Variable | Default | Description |
|---|---|---|
| `LLM_CACHE_ENABLED` | `true` | Toggle response cache |
| `LLM_CACHE_MAX_SIZE` | `256` | Max cached prompts (LRU eviction) |
| `LLM_CACHE_TTL_SECONDS` | `3600` | Cache entry lifetime |

Prefix a prompt with `nocache:` to bypass the cache for a specific call.

## Qdrant Connection Pool

| Variable | Default |
|---|---|
| `QDRANT_MAX_CONNECTIONS` | `10` |
| `QDRANT_TIMEOUT_SECONDS` | `30` |

## Adaptive Learning

| Variable | Default | Description |
|---|---|---|
| `MLFLOW_TRACKING_URI` | `http://localhost:5000` | MLflow server |
| `MLFLOW_EXPERIMENT_NAME` | `ai-decisioning-weights` | Experiment name |
| `DRIFT_DEFAULT_RATE_THRESHOLD` | `0.05` | Alert if default rate exceeds this |
| `DRIFT_CHECK_INTERVAL_SECONDS` | `3600` | Drift check cadence |

## Fairness Monitoring

| Variable | Default | Description |
|---|---|---|
| `FAIRNESS_DISPARATE_IMPACT_THRESHOLD` | `0.8` | 4/5ths rule threshold |
| `FAIRNESS_MIN_SEGMENT_SIZE` | `30` | Min decisions before a segment is evaluated |
| `FAIRNESS_ALERT_SLACK_WEBHOOK` | `` | Slack webhook URL for violation alerts |
| `FAIRNESS_ALERT_EMAIL` | `` | Email address for violation alerts |

## Example `.env`

```dotenv
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/decisioning
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3
QDRANT_URL=http://localhost:6333
KAFKA_BOOTSTRAP_SERVERS=localhost:9092

ACTIVE_STRATEGY_VERSION=v1.1.0
CHALLENGER_VERSION=v1.2.0
CHALLENGER_TRAFFIC_PCT=20

LLM_CACHE_ENABLED=true
DRIFT_DEFAULT_RATE_THRESHOLD=0.05
FAIRNESS_ALERT_SLACK_WEBHOOK=https://hooks.slack.com/services/xxx/yyy/zzz
```
