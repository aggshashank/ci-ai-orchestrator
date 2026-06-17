"""
LLM factory with optional response cache.

get_llm() returns the provider singleton (unchanged).
cached_llm_invoke(prompt) wraps llm.invoke() with an LRU+TTL response cache
to reduce redundant calls for identical prompts within the TTL window.
"""
import hashlib
import time
from functools import lru_cache

import structlog

from llm.base import LLMProvider
from config import get_settings

logger = structlog.get_logger()

_VALID_PROVIDERS = ("ollama", "groq", "openai", "azure")

# Response cache: prompt_hash -> (response_str, inserted_at_epoch)
_response_cache: dict[str, tuple[str, float]] = {}


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


def cached_llm_invoke(prompt: str) -> str:
    """
    Call the LLM with a response cache keyed by SHA-256 of the prompt.
    Cache entries expire after llm_cache_ttl_seconds.
    When the cache is full (> llm_cache_max_size), evict the oldest entry.

    Bypass: set LLM_CACHE_ENABLED=false or pass prompt starting with
    'nocache:' to skip caching for that call.
    """
    settings = get_settings()

    if not settings.llm_cache_enabled or prompt.startswith("nocache:"):
        return get_llm().invoke(prompt)

    ttl     = settings.llm_cache_ttl_seconds
    maxsize = settings.llm_cache_max_size
    key     = hashlib.sha256(prompt.encode()).hexdigest()[:32]
    now     = time.monotonic()

    cached = _response_cache.get(key)
    if cached is not None:
        response, inserted = cached
        if now - inserted < ttl:
            logger.debug("llm_cache_hit", key=key[:8])
            return response
        # Expired — remove stale entry
        del _response_cache[key]

    # Evict oldest entry if at capacity
    if len(_response_cache) >= maxsize:
        oldest_key = min(_response_cache, key=lambda k: _response_cache[k][1])
        del _response_cache[oldest_key]

    response = get_llm().invoke(prompt)
    _response_cache[key] = (response, now)
    logger.debug("llm_cache_miss", key=key[:8], cache_size=len(_response_cache))
    return response


def check_llm_health() -> dict:
    """Provider-aware health check — only meaningful for Ollama."""
    provider = get_settings().llm_provider.lower()
    if provider == "ollama":
        from llm.ollama_provider import check_ollama_health
        return check_ollama_health()
    return {"status": "ok", "provider": provider}
