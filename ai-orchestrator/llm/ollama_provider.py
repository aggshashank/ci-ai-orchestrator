import httpx
import structlog
from functools import lru_cache
from langchain_ollama import OllamaLLM, OllamaEmbeddings
from config import get_settings

logger = structlog.get_logger()


@lru_cache()
def create_llm() -> OllamaLLM:
    settings = get_settings()
    logger.info("Initialising Ollama LLM",
                base_url=settings.ollama_base_url, model=settings.ollama_model)
    return OllamaLLM(
        base_url=settings.ollama_base_url,
        model=settings.ollama_model,
        format="json",
        temperature=0.0,
        num_predict=1024,
    )


@lru_cache()
def create_embeddings() -> OllamaEmbeddings:
    settings = get_settings()
    logger.info("Initialising Ollama Embeddings", model=settings.ollama_embed_model)
    return OllamaEmbeddings(
        base_url=settings.ollama_base_url,
        model=settings.ollama_embed_model,
    )


def check_ollama_health() -> dict:
    """Verify Ollama is running and both LLM + embedding models are pulled."""
    settings = get_settings()
    try:
        resp = httpx.get(f"{settings.ollama_base_url}/api/tags", timeout=5)
        resp.raise_for_status()
        available = [m["name"] for m in resp.json().get("models", [])]
        model_ready = any(settings.ollama_model in m for m in available)
        embed_ready = any(settings.ollama_embed_model in m for m in available)
        return {
            "status": "ok" if (model_ready and embed_ready) else "missing_models",
            "llm_model": settings.ollama_model,
            "llm_ready": model_ready,
            "embed_model": settings.ollama_embed_model,
            "embed_ready": embed_ready,
            "available_models": available,
        }
    except Exception as e:
        return {"status": "unreachable", "error": str(e)}
