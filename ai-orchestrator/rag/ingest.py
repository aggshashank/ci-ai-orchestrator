"""
Policy Document Ingestion
--------------------------
Loads policy .txt files, chunks them, generates embeddings via Ollama,
and stores in Qdrant. Idempotent — recreates collection on each run.

Run:
  python -m rag.ingest
"""
import os
import sys
from pathlib import Path
import structlog
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from langchain_text_splitters import RecursiveCharacterTextSplitter
from llm.embeddings import get_embeddings
from config import get_settings

logger = structlog.get_logger()


def ingest():
    settings = get_settings()
    docs_path = Path(settings.policy_docs_path)

    if not docs_path.exists():
        logger.error("Policy docs path not found", path=str(docs_path))
        sys.exit(1)

    client = QdrantClient(url=settings.qdrant_url)
    embeddings = get_embeddings()

    # Recreate collection (idempotent)
    collections = [c.name for c in client.get_collections().collections]
    if settings.qdrant_collection in collections:
        client.delete_collection(settings.qdrant_collection)
        logger.info("Deleted existing collection", name=settings.qdrant_collection)

    # nomic-embed-text produces 768-dim vectors
    client.create_collection(
        collection_name=settings.qdrant_collection,
        vectors_config=VectorParams(size=768, distance=Distance.COSINE),
    )
    logger.info("Created Qdrant collection", name=settings.qdrant_collection)

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=512,
        chunk_overlap=50,
        separators=["\n\n", "\n", ". ", " "],
    )

    points = []
    point_id = 0

    for txt_file in sorted(docs_path.glob("*.txt")):
        text = txt_file.read_text(encoding="utf-8")
        chunks = splitter.split_text(text)
        logger.info("Chunked document", file=txt_file.name, chunks=len(chunks))

        for chunk in chunks:
            vector = embeddings.embed_query(chunk)
            points.append(PointStruct(
                id=point_id,
                vector=vector,
                payload={"text": chunk, "source": txt_file.name},
            ))
            point_id += 1

    if not points:
        logger.error("No chunks generated — check policy-documents/ directory")
        sys.exit(1)

    # Batch upsert
    client.upsert(collection_name=settings.qdrant_collection, points=points)
    logger.info("Ingestion complete",
                total_chunks=len(points),
                collection=settings.qdrant_collection)


if __name__ == "__main__":
    ingest()
