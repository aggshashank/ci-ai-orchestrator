"""
AI Orchestrator — FastAPI entry point
"""
import json
import threading
import structlog
from datetime import datetime, timezone
from pathlib import Path
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from prometheus_client import Counter, Histogram, Gauge, make_asgi_app
from llm_provider import check_ollama_health
from messaging.consumer import start_consumer
from config import get_settings

logger = structlog.get_logger()
settings = get_settings()
AUDIT_LOG = Path("audit_log.jsonl")

app = FastAPI(title="AI Credit Decisioning Orchestrator", version="1.0.0")

# ── Prometheus metrics ────────────────────────────────────────────────────────
AGENT_LATENCY    = Histogram("agent_execution_seconds", "Agent latency", ["agent"])
RECOMMENDATION   = Counter("recommendation_total", "Recommendations", ["recommendation"])
TOKEN_USAGE      = Counter("llm_token_usage_total", "Token usage", ["agent", "token_type"])
MANUAL_REVIEW_Q  = Gauge("manual_review_pending", "Pending manual reviews")

metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)

# ── Startup ───────────────────────────────────────────────────────────────────
@app.on_event("startup")
def startup():
    health = check_ollama_health()
    if health["status"] != "ok":
        logger.warning("Ollama not fully ready", details=health)
    else:
        logger.info("Ollama ready", model=settings.ollama_model,
                    embed_model=settings.ollama_embed_model)

    thread = threading.Thread(target=start_consumer, daemon=True)
    thread.start()
    logger.info("Kafka consumer thread started")

# ── Health ────────────────────────────────────────────────────────────────────
@app.get("/health")
def health():
    ollama = check_ollama_health()
    return {"status": "ok", "ollama": ollama}

# ── Review queue helpers ──────────────────────────────────────────────────────
def _load_audit_records() -> list[dict]:
    if not AUDIT_LOG.exists():
        return []
    records = []
    for line in AUDIT_LOG.read_text().splitlines():
        line = line.strip()
        if line:
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return records


def _save_audit_records(records: list[dict]):
    with open(AUDIT_LOG, "w") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")

# ── HITL endpoints ────────────────────────────────────────────────────────────
@app.get("/api/v1/review-queue")
def review_queue():
    records = _load_audit_records()
    pending = [
        {
            "correlationId": r["correlation_id"],
            "receivedAt": r["timestamp"],
            "recommendation": r["recommendation"],
            "confidence": r["confidence"],
            "summary": r.get("explanation", {}).get("plain_language_summary", ""),
            "adverse_codes": [c["code"] for c in
                              r.get("explanation", {}).get("adverse_action_codes", [])],
        }
        for r in records
        if r.get("recommendation") == "MANUAL_REVIEW" and r.get("human_decision") is None
    ]
    MANUAL_REVIEW_Q.set(len(pending))
    return {"count": len(pending), "items": pending}


class ReviewDecision(BaseModel):
    decision: str     # APPROVE | DECLINE
    reviewer: str
    notes: str = ""


@app.post("/api/v1/review/{correlation_id}/decision")
def submit_decision(correlation_id: str, body: ReviewDecision):
    if body.decision not in ("APPROVE", "DECLINE"):
        raise HTTPException(400, "decision must be APPROVE or DECLINE")

    records = _load_audit_records()
    updated = False
    for r in records:
        if r["correlation_id"] == correlation_id:
            r["human_decision"] = body.decision
            r["reviewer"] = body.reviewer
            r["reviewer_notes"] = body.notes
            r["decided_at"] = datetime.now(timezone.utc).isoformat()
            updated = True
            break

    if not updated:
        raise HTTPException(404, f"correlationId {correlation_id} not found")

    _save_audit_records(records)
    RECOMMENDATION.labels(recommendation=f"HUMAN_{body.decision}").inc()
    logger.info("Human decision recorded", correlation_id=correlation_id,
                decision=body.decision, reviewer=body.reviewer)
    return {"status": "recorded", "correlationId": correlation_id,
            "decision": body.decision}


@app.get("/api/v1/audit/{correlation_id}")
def get_audit(correlation_id: str):
    records = _load_audit_records()
    for r in records:
        if r["correlation_id"] == correlation_id:
            return r
    raise HTTPException(404, f"correlationId {correlation_id} not found")
