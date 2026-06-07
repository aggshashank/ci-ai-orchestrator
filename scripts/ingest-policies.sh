#!/bin/bash
# Ingest policy documents into Qdrant.
# Expects QDRANT_URL and OLLAMA_BASE_URL to be set.
set -e

echo "[ingest-policies] Starting policy document ingestion..."
cd /app

# Retry up to 3 times — Ollama may need a moment to serve the embedding model
MAX_RETRIES=3
for attempt in $(seq 1 $MAX_RETRIES); do
    if python -m rag.ingest; then
        echo "[ingest-policies] Ingestion complete."
        exit 0
    fi
    echo "[ingest-policies] Attempt ${attempt}/${MAX_RETRIES} failed, retrying in 10s..."
    sleep 10
done

echo "[ingest-policies] WARNING: ingestion failed after ${MAX_RETRIES} attempts."
echo "[ingest-policies] RAG will be unavailable until policies are ingested manually."
# Exit 0 so docker-compose does not block ai-orchestrator startup
exit 0
