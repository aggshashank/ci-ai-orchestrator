import structlog
from functools import lru_cache
from llm.base import LLMProvider
from config import get_settings

logger = structlog.get_logger()

_VALID_PROVIDERS = ("ollama", "groq", "openai", "azure")


@lru_cache()
def get_llm() -> LLMProvider:
    """Return a cached LLMProvider for the configured LLM_PROVIDER.

    All returned objects satisfy invoke(str) -> str so agents need no changes.
    """
    provider = get_settings().llm_provider.lower()
    if provider not in _VALID_PROVIDERS:
        raise ValueError(
            f"Unknown LLM_PROVIDER: {provider!r}. Valid options: {', '.join(_VALID_PROVIDERS)}"
        )
    logger.info("LLM provider selected", provider=provider)

    if provider == "ollama":
        from llm.ollama_provider import create_llm
    elif provider == "groq":
        from llm.groq_provider import create_llm
    elif provider == "openai":
        from llm.openai_provider import create_llm
    else:
        from llm.azure_provider import create_llm

    return create_llm()


def check_llm_health() -> dict:
    """Provider-aware health check — only meaningful for Ollama."""
    provider = get_settings().llm_provider.lower()
    if provider == "ollama":
        from llm.ollama_provider import check_ollama_health
        return check_ollama_health()
    return {"status": "ok", "provider": provider}
