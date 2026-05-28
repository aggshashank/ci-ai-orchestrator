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

    # Ollama — local LLM, no API key
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3:latest"
    ollama_embed_model: str = "nomic-embed-text"

    # Qdrant
    qdrant_url: str = "http://localhost:6333"
    qdrant_collection: str = "policy_docs"

    # Policy docs
    policy_docs_path: str = "../policy-documents"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
