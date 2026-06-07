"""
AI Orchestrator - FastAPI entry point
"""
import threading
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, HTTPException
from prometheus_client import Counter, Gauge, Histogram, make_asgi_app
from pydantic import BaseModel

from logging_config import configure_logging, correlation_middleware

configure_logging()

from config import get_settings
from db.repository import DecisionRepository
from db.session import close_db, get_session, init_db
from llm.factory import check_llm_health
from messaging.consumer import start_consumer

logger = structlog.get_logger()
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()

    health = check_llm_health()
    if health["status"] != "ok":
        logger.warning("LLM provider not fully ready", details=health)
    else:
        logger.info("LLM provider ready", provider=settings.llm_provider)

    thread = threading.Thread(target=start_consumer, daemon=True)
    thread.start()
    logger.info("Kafka consumer thread started")

    yield

    await close_db()


app = FastAPI(
    title="AI Credit Decisioning Orchestrator",
    version="1.0.0",
    lifespan=lifespan,
)
app.middleware("http")(correlation_middleware)

AGENT_LATENCY = Histogram("agent_execution_seconds", "Agent latency", ["agent"])
RECOMMENDATION = Counter("recommendation_total", "Recommendations", ["recommendation"])
TOKEN_USAGE = Counter("llm_token_usage_total", "Token usage", ["agent", "token_type"])
MANUAL_REVIEW_Q = Gauge("manual_review_pending", "Pending manual reviews")

metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)


@app.get("/health")
def health():
    llm = check_llm_health()
    return {"status": "ok", "llm": llm}


@app.get("/api/v1/review-queue")
async def review_queue():
    async with get_session() as session:
        repo = DecisionRepository(session)
        pending = await repo.get_pending_review_queue()

    MANUAL_REVIEW_Q.set(len(pending))

    items = [
        {
            "correlationId": d.correlation_id,
            "receivedAt": d.created_at.isoformat(),
            "recommendation": d.recommendation,
            "confidence": d.confidence,
            "summary": "",
            "adverse_codes": [a.code for a in d.adverse_actions],
        }
        for d in pending
    ]
    return {"count": len(items), "items": items}


class ReviewDecision(BaseModel):
    decision: str
    reviewer: str
    notes: str = ""


@app.post("/api/v1/review/{correlation_id}/decision")
async def submit_decision(correlation_id: str, body: ReviewDecision):
    if body.decision not in ("APPROVE", "DECLINE"):
        raise HTTPException(400, "decision must be APPROVE or DECLINE")

    async with get_session() as session:
        repo = DecisionRepository(session)
        updated = await repo.apply_human_decision(
            correlation_id=correlation_id,
            human_decision=body.decision,
            reviewer=body.reviewer,
            reviewer_notes=body.notes,
        )

    if not updated:
        raise HTTPException(404, f"correlationId {correlation_id} not found")

    RECOMMENDATION.labels(recommendation=f"HUMAN_{body.decision}").inc()
    logger.info(
        "Human decision recorded",
        correlation_id=correlation_id,
        decision=body.decision,
    )
    return {
        "status": "recorded",
        "correlationId": correlation_id,
        "decision": body.decision,
    }


@app.get("/api/v1/audit/{correlation_id}")
async def get_audit(correlation_id: str):
    async with get_session() as session:
        repo = DecisionRepository(session)
        decision = await repo.get_by_correlation_id(correlation_id)

    if not decision:
        raise HTTPException(404, f"correlationId {correlation_id} not found")

    agent_map = {ao.agent_name: ao.output_json for ao in decision.agent_outputs}
    return {
        "correlation_id": decision.correlation_id,
        "timestamp": decision.created_at.isoformat(),
        "recommendation": decision.recommendation,
        "confidence": decision.confidence,
        "composite_score": decision.composite_score,
        "application": decision.application_json,
        "credit_result": agent_map.get("credit_agent", {}),
        "fraud_result": agent_map.get("fraud_agent", {}),
        "policy_context": agent_map.get("policy_rag_agent", {}),
        "explanation": agent_map.get("explainability_agent", {}),
        "adverse_actions": [
            {"code": a.code, "description": a.description}
            for a in decision.adverse_actions
        ],
        "human_decision": decision.human_decision,
        "reviewer": decision.reviewer,
        "reviewer_notes": decision.reviewer_notes,
        "decided_at": decision.decided_at.isoformat() if decision.decided_at else None,
    }
