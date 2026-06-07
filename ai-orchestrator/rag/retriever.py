import sys
from pathlib import Path

import structlog
from qdrant_client import QdrantClient

from config import get_settings
from llm.embeddings import get_embeddings

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

logger = structlog.get_logger()


class QdrantRetriever:
    def __init__(self):
        settings = get_settings()
        self.client = QdrantClient(url=settings.qdrant_url)
        self.collection = settings.qdrant_collection
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
