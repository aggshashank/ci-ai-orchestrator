from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Kafka
    kafka_bootstrap_servers: str = "localhost:9092"
    kafka_group_id: str = "ai-orchestrator-group"
    kafka_topic_application_received: str = "application.received"
    kafka_topic_dlq: str = "application.dlq"
    kafka_topic_manual_review: str = "manual.review.required"
    kafka_topic_decision_completed: str = "decision.completed"

    # LLM provider selection
    llm_provider: str = "ollama"          # ollama | groq | openai | azure
    embed_provider: str = "ollama"        # ollama | openai | azure

    # Ollama — local LLM, no API key
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3:latest"
    ollama_embed_model: str = "nomic-embed-text"

    # Groq
    groq_api_key: str = ""
    groq_model: str = "llama3-8b-8192"

    # OpenAI
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    openai_embed_model: str = "text-embedding-3-small"

    # Azure OpenAI
    azure_openai_api_key: str = ""
    azure_openai_endpoint: str = ""
    azure_openai_deployment: str = ""
    azure_openai_api_version: str = "2024-02-01"
    azure_embed_deployment: str = ""

    # Qdrant
    qdrant_url: str = "http://localhost:6333"
    qdrant_collection: str = "policy_docs"

    # PostgreSQL
    database_url: str = "postgresql+asyncpg://poc:poc@localhost:5432/decisions"

    # Policy docs
    policy_docs_path: str = "../policy-documents"

    # Rules engine
    strategy_version: str = "v1.0.0"   # subdirectory under strategies_dir to load
    strategies_dir: str = "strategies"  # relative to ai-orchestrator/
    redis_url: str = ""                 # empty = no Redis, use file cache only
    rules_cache_ttl: int = 300          # seconds; informational for future TTL-aware loader

    # Experimentation (champion/challenger)
    experiment_enabled: bool = False
    experiment_challenger_strategy: str = ""      # e.g. "v1.1.0"
    experiment_challenger_percentage: int = 10    # % of traffic routed to challenger
    experiment_significance_threshold: float = 0.05
    experiment_min_sample_size: int = 100

    # Prompt versions — set via env var to hot-swap without redeployment
    credit_agent_prompt_version: str = "v1"
    fraud_agent_prompt_version: str = "v1"
    policy_rag_agent_prompt_version: str = "v1"
    explainability_agent_prompt_version: str = "v1"
    limit_review_agent_prompt_version: str = "v1"
    treatment_agent_prompt_version: str = "v1"
    propensity_agent_prompt_version: str = "v1"

    # Kafka topics for non-origination workflows
    kafka_topic_limit_review: str = "limit.review.triggered"
    kafka_topic_delinquency_treatment: str = "delinquency.treatment.triggered"
    kafka_topic_cross_sell: str = "cross_sell.eligible"

    # Kafka topics — outcome events (Task 3.3)
    kafka_topic_outcome_default: str = "outcome.account_default"
    kafka_topic_outcome_fraud: str = "outcome.fraud_confirmed"
    kafka_topic_outcome_payoff: str = "outcome.early_payoff"

    # MLflow tracking (Task 3.3)
    mlflow_tracking_uri: str = "http://localhost:5000"
    mlflow_experiment_name: str = "ai-decisioning-weights"

    # Drift detection (Task 3.3)
    drift_default_rate_threshold: float = 0.05   # alert if >5% of APPROVEs default
    drift_check_interval_seconds: int = 3600     # hourly

    # LLM response cache (Task 3.5)
    llm_cache_enabled: bool = True
    llm_cache_max_size: int = 256
    llm_cache_ttl_seconds: int = 3600

    # Qdrant connection pool (Task 3.5)
    qdrant_max_connections: int = 10
    qdrant_timeout_seconds: int = 30

    # Fairness monitoring (Task 3.4)
    fairness_disparate_impact_threshold: float = 0.8   # 4/5ths rule
    fairness_min_segment_size: int = 30
    fairness_alert_slack_webhook: str = ""
    fairness_alert_email: str = ""

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
