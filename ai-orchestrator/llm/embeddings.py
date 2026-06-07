import structlog
from functools import lru_cache
from config import get_settings

logger = structlog.get_logger()

_VALID_PROVIDERS = ("ollama", "openai", "azure")


@lru_cache()
def get_embeddings():
    """Return a cached embeddings instance for the configured EMBED_PROVIDER."""
    settings = get_settings()
    provider = settings.embed_provider.lower()

    if provider not in _VALID_PROVIDERS:
        raise ValueError(
            f"Unknown EMBED_PROVIDER: {provider!r}. Valid options: {', '.join(_VALID_PROVIDERS)}"
        )

    if provider == "ollama":
        from llm.ollama_provider import create_embeddings
        return create_embeddings()

    if provider == "openai":
        from langchain_openai import OpenAIEmbeddings
        logger.info("Initialising OpenAI Embeddings", model=settings.openai_embed_model)
        return OpenAIEmbeddings(
            api_key=settings.openai_api_key,
            model=settings.openai_embed_model,
        )

    # azure
    from langchain_openai import AzureOpenAIEmbeddings
    logger.info("Initialising Azure OpenAI Embeddings",
                deployment=settings.azure_embed_deployment)
    return AzureOpenAIEmbeddings(
        api_key=settings.azure_openai_api_key,
        azure_endpoint=settings.azure_openai_endpoint,
        azure_deployment=settings.azure_embed_deployment,
        api_version=settings.azure_openai_api_version,
    )
