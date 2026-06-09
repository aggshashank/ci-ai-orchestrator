"""
SimulationEngine: re-score historical decisions using a new strategy version.

All computation is deterministic — LLM agents are NOT called. The engine
replays the risk_decision_agent scoring formula against stored agent outputs,
giving a fast, reproducible comparison.
"""
from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from typing import Any

import structlog

from db.session import get_session
from simulation.comparator import chi_squared_p_value
from simulation.models import (
    ChangedDecision,
    RecommendationDistribution,
    SimulationRequest,
)
from simulation.report import generate_html_report
from strategy.manager import engine_from_snapshot, score_deterministically

logger = structlog.get_logger()

_DATE_RANGES = {
    "last_7_days":  7,
    "last_30_days": 30,
    "last_90_days": 90,
    "all": None,
}


async def create_and_launch(request: SimulationRequest) -> str:
    """
    Persist a pending simulation row, schedule the background work, return the ID.
    """
    from db.models import Simulation as SimORM

    sim_id = str(uuid.uuid4())
    async with get_session() as session:
        session.add(SimORM(
            id=sim_id,
            strategy_version=request.strategy_version,
            sample_size=request.sample_size,
            date_range=request.date_range,
            status="pending",
        ))

    asyncio.create_task(_run(sim_id, request))
    return sim_id


async def _run(sim_id: str, request: SimulationRequest) -> None:
    """Background coroutine that executes the simulation and writes results."""
    from db.models import Simulation as SimORM
    from sqlalchemy import select

    logger.info("simulation_start", simulation_id=sim_id,
                strategy_version=request.strategy_version)

    # Mark running
    async with get_session() as session:
        result = await session.execute(select(SimORM).where(SimORM.id == sim_id))
        sim = result.scalar_one_or_none()
        if sim:
            sim.status = "running"

    try:
        # Load strategy snapshot from DB
        snapshot, snapshot_version = await _load_snapshot(request.strategy_version)
        engine = engine_from_snapshot(snapshot, snapshot_version)

        # Sample historical decisions
        decisions = await _sample_decisions(request)
        if not decisions:
            await _fail(sim_id, "No historical decisions found matching the query criteria.")
            return

        # Score each decision under the new strategy
        baseline_counter: dict[str, int] = {}
        simulated_counter: dict[str, int] = {}
        changed: list[ChangedDecision] = []

        for d in decisions:
            orig = d["recommendation"]
            baseline_counter[orig] = baseline_counter.get(orig, 0) + 1

            credit  = d["agent_outputs"].get("credit_agent", {})
            fraud   = d["agent_outputs"].get("fraud_agent", {})
            policy  = d["agent_outputs"].get("policy_rag_agent", {})

            new_rec, _, _ = score_deterministically(engine, credit, fraud, policy)
            simulated_counter[new_rec] = simulated_counter.get(new_rec, 0) + 1

            if new_rec != orig:
                changed.append(ChangedDecision(
                    correlation_id=d["correlation_id"],
                    original=orig,
                    simulated=new_rec,
                ))

        p_value = chi_squared_p_value(baseline_counter, simulated_counter)
        baseline_dist = RecommendationDistribution.from_counter(baseline_counter)
        simulated_dist = RecommendationDistribution.from_counter(simulated_counter)

        report_html = generate_html_report(
            simulation_id=sim_id,
            strategy_version=request.strategy_version,
            baseline=baseline_dist,
            simulated=simulated_dist,
            changed=changed,
            p_value=p_value,
            sample_size=len(decisions),
            date_range=request.date_range,
        )

        async with get_session() as session:
            result = await session.execute(select(SimORM).where(SimORM.id == sim_id))
            sim = result.scalar_one_or_none()
            if sim:
                sim.status = "complete"
                sim.baseline_distribution = baseline_counter
                sim.simulated_distribution = simulated_counter
                sim.changed_decisions = [c.model_dump() for c in changed]
                sim.p_value = p_value
                sim.report_html = report_html
                sim.completed_at = datetime.now(timezone.utc)

        logger.info("simulation_complete", simulation_id=sim_id,
                    changed=len(changed), p_value=round(p_value, 4))

    except Exception as exc:
        logger.error("simulation_failed", simulation_id=sim_id, error=str(exc))
        await _fail(sim_id, str(exc))


async def _load_snapshot(version: str) -> tuple[dict[str, Any], str]:
    """Load the rules snapshot from strategy_versions table."""
    from db.models import StrategyVersionRecord as SVR
    from sqlalchemy import select

    async with get_session() as session:
        result = await session.execute(select(SVR).where(SVR.version == version))
        row = result.scalar_one_or_none()

    if row is None:
        raise ValueError(
            f"Strategy version '{version}' is not registered. "
            "POST to /api/v1/strategies/{version}/activate first."
        )
    return row.rules_snapshot, row.version


async def _sample_decisions(request: SimulationRequest) -> list[dict[str, Any]]:
    """Fetch historical decisions with agent outputs for scoring."""
    from db.models import AgentOutput, Decision
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    days = _DATE_RANGES.get(request.date_range)

    async with get_session() as session:
        stmt = (
            select(Decision)
            .options(selectinload(Decision.agent_outputs))
            .order_by(Decision.created_at.desc())
            .limit(request.sample_size)
        )
        if days is not None:
            from sqlalchemy import func, interval  # type: ignore[attr-defined]
            cutoff = func.now() - func.cast(f"{days} days", interval)  # type: ignore[operator]
            stmt = stmt.where(Decision.created_at >= cutoff)

        result = await session.execute(stmt)
        rows = result.scalars().all()

        return [
            {
                "correlation_id": d.correlation_id,
                "recommendation": d.recommendation,
                "agent_outputs": {ao.agent_name: ao.output_json for ao in d.agent_outputs},
            }
            for d in rows
        ]


async def _fail(sim_id: str, message: str) -> None:
    from db.models import Simulation as SimORM
    from sqlalchemy import select

    async with get_session() as session:
        result = await session.execute(select(SimORM).where(SimORM.id == sim_id))
        sim = result.scalar_one_or_none()
        if sim:
            sim.status = "failed"
            sim.error_message = message
            sim.completed_at = datetime.now(timezone.utc)
