import sys
from pathlib import Path
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import structlog
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams
from llm.embeddings import get_embeddings
from config import get_settings

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

            # qdrant-client 1.10+ uses query_points() — search() was removed
            results = self.client.query_points(
                collection_name=self.collection,
                query=query_vector,
                limit=k,
                with_payload=True,
            ).points

            chunks = [r.payload.get("text", "") for r in results if r.payload]
            logger.info("qdrant_retriever", query_preview=query[:60],
                        chunks_returned=len(chunks))
            return chunks

        except Exception as e:
            logger.error("qdrant_retriever failed", error=str(e))
            return []
