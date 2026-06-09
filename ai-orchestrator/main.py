"""
AI Orchestrator - FastAPI entry point
"""
import asyncio
import threading
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse
from prometheus_client import Counter, Gauge, Histogram, make_asgi_app
from pydantic import BaseModel

from logging_config import configure_logging, correlation_middleware

configure_logging()

from config import get_settings
from db.repository import DecisionRepository, SimulationRepository
from db.session import close_db, get_session, init_db
from experimentation.promoter import run_promotion_loop
from experimentation.tracker import ExperimentTracker, format_stats_response
from llm.factory import check_llm_health
from messaging.consumer import start_consumer
from simulation.engine import create_and_launch
from simulation.models import SimulationRequest, SimulationResult
from strategy.diff import diff_strategies
from strategy.manager import engine_from_snapshot, score_deterministically, take_snapshot
from strategy.registry import StrategyRegistry

logger = structlog.get_logger()
settings = get_settings()


async def _validate_prompts() -> None:
    """Fail fast on startup if any configured prompt version file is missing."""
    try:
        from prompts.registry import get_prompt_registry
        registry = get_prompt_registry()
        registry.validate_all({
            "credit_agent":          settings.credit_agent_prompt_version,
            "fraud_agent":           settings.fraud_agent_prompt_version,
            "policy_rag_agent":      settings.policy_rag_agent_prompt_version,
            "explainability_agent":  settings.explainability_agent_prompt_version,
        })
        logger.info("prompt_versions_validated")
    except FileNotFoundError as exc:
        logger.error("prompt_validation_failed", error=str(exc))
        raise RuntimeError(str(exc)) from exc


async def _register_strategy_version() -> None:
    """Idempotent: snapshot current YAML rules and register in DB on startup."""
    try:
        snapshot = take_snapshot()
        metadata = {"changelog": [f"Auto-registered on startup: {settings.strategy_version}"]}
        async with get_session() as session:
            reg = StrategyRegistry(session)
            record = await reg.register(
                version=settings.strategy_version,
                snapshot=snapshot,
                changelog=metadata["changelog"],
            )
            if not record.is_active:
                await reg.set_active(settings.strategy_version)
        logger.info("strategy_version_registered", version=settings.strategy_version)
    except Exception as exc:
        logger.warning("strategy_version_registration_failed", error=str(exc))


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    await _register_strategy_version()
    await _validate_prompts()

    if settings.experiment_enabled and settings.experiment_challenger_strategy:
        asyncio.create_task(run_promotion_loop())
        logger.info(
            "experiment_promotion_loop_started",
            challenger=settings.experiment_challenger_strategy,
            challenger_pct=settings.experiment_challenger_percentage,
        )

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
        "strategy_version": decision.strategy_version,
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


# ── Strategy Version Management ───────────────────────────────────────────────

@app.get("/api/v1/strategies")
async def list_strategies():
    async with get_session() as session:
        reg = StrategyRegistry(session)
        versions = await reg.list_versions()
    return {
        "count": len(versions),
        "versions": [
            {
                "version": v.version,
                "is_active": v.is_active,
                "activated_at": v.activated_at.isoformat() if v.activated_at else None,
                "created_at": v.created_at.isoformat(),
                "changelog": v.changelog,
            }
            for v in versions
        ],
    }


# NOTE: /diff must be declared BEFORE /{version} so FastAPI does not treat
# the literal path segment "diff" as a version parameter.
@app.get("/api/v1/strategies/diff")
async def strategy_diff(
    from_version: str = Query(alias="from"),
    to_version: str = Query(alias="to"),
):
    async with get_session() as session:
        reg = StrategyRegistry(session)
        from_rec = await reg.get_by_version(from_version)
        to_rec = await reg.get_by_version(to_version)

    if not from_rec:
        raise HTTPException(404, f"Strategy version '{from_version}' not found")
    if not to_rec:
        raise HTTPException(404, f"Strategy version '{to_version}' not found")

    result = diff_strategies(
        from_version=from_version,
        from_snapshot=from_rec.rules_snapshot,
        to_version=to_version,
        to_snapshot=to_rec.rules_snapshot,
    )
    return result.model_dump()


@app.get("/api/v1/strategies/{version}")
async def get_strategy(version: str):
    async with get_session() as session:
        reg = StrategyRegistry(session)
        record = await reg.get_by_version(version)

    if not record:
        raise HTTPException(404, f"Strategy version '{version}' not found")
    return record.model_dump()


@app.post("/api/v1/decisions/{correlation_id}/replay")
async def replay_decision(correlation_id: str):
    """
    Re-score a stored decision using the strategy version that was active
    when it was made. Returns the replayed result alongside the original.
    All computation is deterministic — no LLM calls.
    """
    async with get_session() as session:
        repo = DecisionRepository(session)
        decision = await repo.get_by_correlation_id(correlation_id)

    if not decision:
        raise HTTPException(404, f"correlationId {correlation_id} not found")

    async with get_session() as session:
        reg = StrategyRegistry(session)
        strategy_rec = await reg.get_by_version(decision.strategy_version)

    if not strategy_rec:
        raise HTTPException(
            404,
            f"Strategy version '{decision.strategy_version}' not in registry. "
            "Cannot reproduce this decision.",
        )

    agent_map = {ao.agent_name: ao.output_json for ao in decision.agent_outputs}
    credit = agent_map.get("credit_agent", {})
    fraud  = agent_map.get("fraud_agent", {})
    policy = agent_map.get("policy_rag_agent", {})

    engine = engine_from_snapshot(strategy_rec.rules_snapshot, strategy_rec.version)
    replayed_rec, replayed_conf, replayed_composite = score_deterministically(
        engine, credit, fraud, policy
    )

    return {
        "correlation_id": correlation_id,
        "strategy_version": decision.strategy_version,
        "original_recommendation": decision.recommendation,
        "original_confidence": decision.confidence,
        "original_composite_score": decision.composite_score,
        "replayed_recommendation": replayed_rec,
        "replayed_confidence": replayed_conf,
        "replayed_composite_score": replayed_composite,
        "changed": replayed_rec != decision.recommendation,
    }


# ── Decision Simulation Engine ────────────────────────────────────────────────

@app.post("/api/v1/simulations", status_code=202)
async def create_simulation(body: SimulationRequest):
    """
    Launch a background simulation. Returns immediately with a simulation_id.
    Poll GET /api/v1/simulations/{id} for status and results.
    """
    async with get_session() as session:
        reg = StrategyRegistry(session)
        record = await reg.get_by_version(body.strategy_version)

    if not record:
        raise HTTPException(
            404,
            f"Strategy version '{body.strategy_version}' not registered. "
            "Use GET /api/v1/strategies to see available versions.",
        )

    sim_id = await create_and_launch(body)
    return {
        "simulation_id": sim_id,
        "status": "pending",
        "strategy_version": body.strategy_version,
        "message": f"Simulation queued. Poll GET /api/v1/simulations/{sim_id} for results.",
    }


@app.get("/api/v1/simulations/{sim_id}")
async def get_simulation(sim_id: str):
    async with get_session() as session:
        sim_repo = SimulationRepository(session)
        sim = await sim_repo.get(sim_id)

    if not sim:
        raise HTTPException(404, f"Simulation '{sim_id}' not found")

    changed = sim.changed_decisions or []
    baseline = sim.baseline_distribution or {}
    simulated = sim.simulated_distribution or {}

    change_rate = (
        round(len(changed) / max(sim.sample_size, 1) * 100, 2)
        if sim.status == "complete"
        else None
    )

    return {
        "simulation_id": sim.id,
        "strategy_version": sim.strategy_version,
        "sample_size": sim.sample_size,
        "date_range": sim.date_range,
        "status": sim.status,
        "baseline_distribution": baseline,
        "simulated_distribution": simulated,
        "changed_count": len(changed),
        "changed_decisions": changed[:50],  # first 50 in API response
        "change_rate_pct": change_rate,
        "p_value": sim.p_value,
        "has_report": sim.report_html is not None,
        "error_message": sim.error_message,
        "created_at": sim.created_at.isoformat(),
        "completed_at": sim.completed_at.isoformat() if sim.completed_at else None,
    }


# ── Champion/Challenger Experiment ───────────────────────────────────────────

@app.get("/api/v1/experiments")
async def get_experiment_stats():
    """
    Return current experiment configuration and live per-variant stats.
    Also refreshes the Prometheus gauges so Grafana panels stay current.
    """
    async with get_session() as session:
        tracker = ExperimentTracker(session)
        stats = await tracker.get_variant_stats()
        await tracker.refresh_prometheus()

    return {
        "experiment_enabled": settings.experiment_enabled,
        "champion_strategy": settings.strategy_version,
        "challenger_strategy": settings.experiment_challenger_strategy,
        "challenger_percentage": settings.experiment_challenger_percentage,
        "significance_threshold": settings.experiment_significance_threshold,
        "min_sample_size": settings.experiment_min_sample_size,
        "variant_stats": format_stats_response(stats),
    }


@app.get("/api/v1/simulations/{sim_id}/report", response_class=HTMLResponse)
async def get_simulation_report(sim_id: str):
    async with get_session() as session:
        sim_repo = SimulationRepository(session)
        sim = await sim_repo.get(sim_id)

    if not sim:
        raise HTTPException(404, f"Simulation '{sim_id}' not found")
    if not sim.report_html:
        raise HTTPException(404, "Report not yet available — simulation may still be running.")

    return HTMLResponse(content=sim.report_html)
