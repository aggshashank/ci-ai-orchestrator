"""
Policy RAG agent (async).
"""
import asyncio
import json
import time

import structlog

from agents.state import GraphState
from config import get_settings
from llm.factory import cached_llm_invoke
from prompts.registry import get_prompt_registry
from rag.retriever import get_retriever

logger = structlog.get_logger()


async def policy_rag_agent(state: GraphState) -> dict:
    start = time.time()
    app = state["application"]
    corr = state["correlation_id"]

    logger.info("policy_rag_agent start", correlation_id=corr)

    query = (
        f"credit score {app.creditScore} "
        f"utilization {app.utilization}% "
        f"address mismatch {app.addressMismatch} "
        f"delinquencies {app.delinquencies or 0}"
    )

    try:
        retriever = get_retriever()
        # Qdrant retrieval is blocking I/O — run in thread pool
        chunks = await asyncio.to_thread(retriever.retrieve, query, 4)

        if not chunks:
            logger.warning("policy_rag_agent: no chunks retrieved", correlation_id=corr)
            return {
                "policy_context": {
                    "policy_applicable": False,
                    "rules": [],
                    "action": "MANUAL_REVIEW",
                    "citations": [],
                }
            }

        policy_text = "\n\n".join(f"[Chunk {i + 1}]: {chunk}" for i, chunk in enumerate(chunks))
        logger.info(
            "policy_rag_agent retrieved chunks",
            correlation_id=corr,
            chunk_count=len(chunks),
        )

        settings = get_settings()
        template = get_prompt_registry().get("policy_rag_agent", settings.policy_rag_agent_prompt_version)
        prompt = template.format(
            credit_score=app.creditScore,
            utilization=app.utilization,
            address_mismatch=str(app.addressMismatch).lower(),
            delinquencies=app.delinquencies or 0,
            policy_chunks=policy_text,
        )

        raw = await asyncio.to_thread(cached_llm_invoke, prompt)
        result = json.loads(raw)

        latency = round(time.time() - start, 2)
        logger.info(
            "policy_rag_agent complete",
            correlation_id=corr,
            action=result.get("action"),
            latency_s=latency,
        )
        return {"policy_context": result}

    except Exception as exc:
        logger.error(
            "policy_rag_agent failed - fallback",
            correlation_id=corr,
            error_type=type(exc).__name__,
        )
        return {
            "policy_context": {
                "policy_applicable": False,
                "rules": [],
                "action": "MANUAL_REVIEW",
                "citations": [],
            }
        }
