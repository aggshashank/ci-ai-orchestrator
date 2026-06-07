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

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
