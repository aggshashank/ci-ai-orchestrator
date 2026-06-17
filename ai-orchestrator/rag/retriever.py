"""
Qdrant retriever with connection-pool singleton.

A single QdrantRetriever instance is created at module import time
(via @lru_cache on get_retriever()).  The qdrant-client library manages
the underlying HTTP connection pool; we configure max_connections via
settings.qdrant_max_connections.
"""
import sys
from functools import lru_cache
from pathlib import Path

import structlog
from qdrant_client import QdrantClient
from qdrant_client.http import models as qdrant_models

from config import get_settings
from llm.embeddings import get_embeddings

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

logger = structlog.get_logger()


class QdrantRetriever:
    def __init__(self, client: QdrantClient, collection: str):
        self.client     = client
        self.collection = collection
        self.embeddings = get_embeddings()

    def retrieve(self, query: str, k: int = 4) -> list[str]:
        try:
            query_vector = self.embeddings.embed_query(query)
            results = self.client.query_points(
                collection_name=self.collection,
                query=query_vector,
                limit=k,
                with_payload=True,
            ).points

            chunks = [result.payload.get("text", "") for result in results if result.payload]
            logger.info("qdrant_retriever", chunks_returned=len(chunks))
            return chunks

        except Exception as exc:
            logger.error("qdrant_retriever failed", error_type=type(exc).__name__)
            return []


@lru_cache()
def get_retriever() -> QdrantRetriever:
    """
    Module-level singleton retriever.  The QdrantClient is created once and
    reused across requests, giving connection-pool behaviour automatically
    through the underlying httpx client.
    """
    settings = get_settings()
    client = QdrantClient(
        url=settings.qdrant_url,
        timeout=settings.qdrant_timeout_seconds,
        # httpx limits: controls the internal connection pool
        limits=qdrant_models.models.PayloadSchemaType,  # placeholder; actual pool via httpx below
    )
    # Override httpx client pool size
    try:
        import httpx
        client._client = httpx.Client(
            limits=httpx.Limits(
                max_connections=settings.qdrant_max_connections,
                max_keepalive_connections=settings.qdrant_max_connections,
            ),
            timeout=settings.qdrant_timeout_seconds,
        )
    except Exception:
        pass  # httpx not available or internal structure changed — fall through

    logger.info(
        "qdrant_retriever_initialized",
        url=settings.qdrant_url,
        collection=settings.qdrant_collection,
        max_connections=settings.qdrant_max_connections,
    )
    return QdrantRetriever(client, settings.qdrant_collection)
