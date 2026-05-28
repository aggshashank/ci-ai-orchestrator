"""
llm_provider.py
---------------
Single place that constructs the LangChain LLM and Embeddings objects.
Uses langchain-ollama (the current non-deprecated package).

Supported local models:
  llama3:latest      ~4.7GB  recommended default
  mistral           ~4.1GB  fast, reliable JSON output
  phi3              ~2.3GB  lightweight, good for 8GB RAM
  llama3.1:70b      ~40GB   best reasoning, needs 32GB+ RAM
  gemma2            ~5.4GB  good instruction following

Embedding models:
  nomic-embed-text  ~274MB  best quality/size ratio for RAG (768-dim)
  mxbai-embed-large ~670MB  higher quality, slightly larger
"""
import sys
from pathlib import Path
_PROJECT_ROOT = Path(__file__).resolve().parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import structlog
from functools import lru_cache
from langchain_ollama import OllamaLLM, OllamaEmbeddings
from config import get_settings

logger = structlog.get_logger()


@lru_cache()
def get_llm() -> OllamaLLM:
    """
    Cached OllamaLLM instance with JSON output enforced.

    format="json" constrains Ollama token sampling to valid JSON —
    equivalent to OpenAI's response_format={"type":"json_object"}.
    temperature=0.0 ensures deterministic output (same input → same JSON).
    """
    settings = get_settings()
    logger.info("Initialising Ollama LLM",
                base_url=settings.ollama_base_url,
                model=settings.ollama_model)
    return OllamaLLM(
        base_url=settings.ollama_base_url,
        model=settings.ollama_model,
        format="json",
        temperature=0.0,
        num_predict=1024,
    )


@lru_cache()
def get_embeddings() -> OllamaEmbeddings:
    """
    Cached OllamaEmbeddings using nomic-embed-text.
    Produces 768-dimensional vectors for Qdrant cosine search.
    """
    settings = get_settings()
    logger.info("Initialising Ollama Embeddings",
                model=settings.ollama_embed_model)
    return OllamaEmbeddings(
        base_url=settings.ollama_base_url,
        model=settings.ollama_embed_model,
    )


def check_ollama_health() -> dict:
    """Verify Ollama is running and both models are pulled."""
    import httpx
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
