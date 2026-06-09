"""
ExperimentPromoter: monitors experiment stats and promotes the challenger
when statistical significance is reached.

Promotion steps:
  1. Mark experiment as "promoted" in experiments table.
  2. Activate challenger strategy in strategy_versions.
  3. Clear LRU caches so the new strategy takes effect at next request.
  4. Log a prominent audit entry and increment Prometheus counter.

The promoter does NOT restart the process — cache clearing is sufficient for
the rules engine and prompt registry to pick up the new active configuration.
After promotion, the EXPERIMENT_ENABLED flag should be toggled off via config
or the next deploy to avoid duplicate experiment data.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import structlog
from prometheus_client import Counter

from config import get_settings
from db.session import get_session
from experimentation.significance import chi_squared_p_value
from experimentation.tracker import ExperimentTracker

logger = structlog.get_logger()

PROMOTION_COUNTER = Counter(
    "experiment_promotion_triggered_total",
    "Number of times a challenger was auto-promoted to champion",
    ["challenger_version"],
)


async def check_and_promote() -> bool:
    """
    Check experiment stats. If significance threshold is met, promote the challenger.
    Returns True if promotion happened.
    """
    settings = get_settings()
    if not settings.experiment_enabled or not settings.experiment_challenger_strategy:
        return False

    async with get_session() as session:
        tracker = ExperimentTracker(session)
        stats = await tracker.get_variant_stats()

    champion_dist = stats.get("champion", {})
    challenger_dist = stats.get("challenger", {})

    champion_total = sum(champion_dist.values())
    challenger_total = sum(challenger_dist.values())

    if challenger_total < settings.experiment_min_sample_size:
        logger.debug(
            "experiment_not_ready",
            challenger_total=challenger_total,
            min_needed=settings.experiment_min_sample_size,
        )
        return False

    p_value = chi_squared_p_value(champion_dist, challenger_dist)
    logger.info(
        "experiment_significance_check",
        p_value=round(p_value, 4),
        threshold=settings.experiment_significance_threshold,
        challenger_total=challenger_total,
    )

    if p_value >= settings.experiment_significance_threshold:
        return False  # not significant yet

    # Promote challenger
    await _promote(settings.experiment_challenger_strategy, p_value)
    return True


async def _promote(challenger_version: str, p_value: float) -> None:
    from db.models import Experiment as ExperimentORM
    from sqlalchemy import select
    from strategy.registry import StrategyRegistry

    now = datetime.now(timezone.utc)

    async with get_session() as session:
        # Mark experiment row as promoted
        stmt = select(ExperimentORM).where(ExperimentORM.status == "active")
        result = await session.execute(stmt)
        experiment = result.scalar_one_or_none()
        if experiment:
            experiment.status = "promoted"
            experiment.promoted_version = challenger_version
            experiment.completed_at = now

        # Activate challenger in strategy registry
        reg = StrategyRegistry(session)
        await reg.set_active(challenger_version)

    # Clear rules engine cache so next request uses the promoted strategy
    from rules.engine import get_challenger_engine, get_rules_engine
    get_rules_engine.cache_clear()
    get_challenger_engine.cache_clear()

    PROMOTION_COUNTER.labels(challenger_version=challenger_version).inc()

    logger.warning(
        "EXPERIMENT_PROMOTED",
        challenger_version=challenger_version,
        p_value=round(p_value, 4),
        action="Challenger promoted to champion. Set EXPERIMENT_ENABLED=false in config.",
    )


async def run_promotion_loop(interval_seconds: int = 60) -> None:
    """Background loop — call from app lifespan."""
    while True:
        await asyncio.sleep(interval_seconds)
        try:
            promoted = await check_and_promote()
            if promoted:
                logger.info("experiment_promotion_loop stopping — promotion complete")
                return  # stop after first promotion
        except Exception as exc:
            logger.error("experiment_promotion_loop_error", error=str(exc))
