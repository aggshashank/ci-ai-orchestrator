"""
Policy RAG Agent
----------------
Retrieves relevant underwriting/fraud policy chunks from Qdrant,
then asks Llama 3.1 to identify applicable rules for this application.

RAG with local embeddings (nomic-embed-text via Ollama):
  - No OpenAI embedding costs
  - nomic-embed-text is purpose-built for retrieval, 768-dim vectors
  - Qdrant cosine similarity search
"""
import json
import time
import structlog
from agents.state import GraphState
from llm.factory import get_llm
from rag.retriever import QdrantRetriever

logger = structlog.get_logger()

POLICY_PROMPT = """\
You are a compliance officer reviewing a credit card application against company policy.

Application summary:
- Credit Score: {credit_score}
- Utilization: {utilization}%
- Address Mismatch: {address_mismatch}
- Delinquencies: {delinquencies}

Relevant policy excerpts retrieved from the policy database:
---
{policy_chunks}
---

Based ONLY on the policy excerpts above, identify which rules apply to this application.
Do NOT use any knowledge outside the provided excerpts.
If no relevant policy is found, set policy_applicable to false.

Return ONLY a JSON object:
{{
  "policy_applicable": true or false,
  "rules": ["exact rule text from policy that applies"],
  "action": "APPROVE" or "MANUAL_REVIEW" or "DECLINE",
  "citations": ["policy document reference for each rule"]
}}
"""


def policy_rag_agent(state: GraphState) -> dict:
    start = time.time()
    app = state["application"]
    corr = state["correlation_id"]

    logger.info("policy_rag_agent start", correlation_id=corr)

    # Build semantic search query from application signals
    query = (
        f"credit score {app.creditScore} "
        f"utilization {app.utilization}% "
        f"address mismatch {app.addressMismatch} "
        f"delinquencies {app.delinquencies or 0}"
    )

    try:
        retriever = QdrantRetriever()
        chunks = retriever.retrieve(query, k=4)

        if not chunks:
            logger.warning("policy_rag_agent: no chunks retrieved",
                           correlation_id=corr)
            return {"policy_context": {
                "policy_applicable": False,
                "rules": [],
                "action": "MANUAL_REVIEW",
                "citations": [],
            }}

        policy_text = "\n\n".join(f"[Chunk {i+1}]: {c}" for i, c in enumerate(chunks))
        logger.info("policy_rag_agent retrieved chunks",
                    correlation_id=corr, chunk_count=len(chunks))

        prompt = POLICY_PROMPT.format(
            credit_score=app.creditScore,
            utilization=app.utilization,
            address_mismatch=str(app.addressMismatch).lower(),
            delinquencies=app.delinquencies or 0,
            policy_chunks=policy_text,
        )

        llm = get_llm()
        raw = llm.invoke(prompt)
        result = json.loads(raw)

        latency = round(time.time() - start, 2)
        logger.info("policy_rag_agent complete", correlation_id=corr,
                    action=result.get("action"), latency_s=latency)
        return {"policy_context": result}

    except Exception as e:
        logger.error("policy_rag_agent failed — fallback",
                     correlation_id=corr, error=str(e))
        return {"policy_context": {
            "policy_applicable": False,
            "rules": [],
            "action": "MANUAL_REVIEW",
            "citations": [],
        }}
