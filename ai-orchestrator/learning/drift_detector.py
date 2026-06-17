"""
Model drift detector.

Monitors the rolling default rate on decisions the model recommended APPROVE.
If the default rate exceeds the configured threshold, emits a Prometheus
counter increment and logs at WARNING level.

Runs as a periodic async task started from main.py lifespan.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import structlog
from prometheus_client import Counter, Gauge

logger = structlog.get_logger()

DRIFT_ALERTS = Counter(
    "model_drift_alerts_total",
    "Number of times the default rate breached the drift threshold",
    ["window_days"],
)
DEFAULT_RATE_GAUGE = Gauge(
    "approve_default_rate",
    "Rolling default rate on APPROVE decisions",
    ["window_days"],
)


async def compute_rolling_default_rate(window_days: int = 30) -> float:
    """
    Returns the fraction of APPROVE decisions in the last window_days that
    subsequently received an ACCOUNT_DEFAULT outcome.
    Returns 0.0 if there are no outcomes in the window.
    """
    from db.session import get_session
    from sqlalchemy import text

    cutoff = (datetime.now(timezone.utc) - timedelta(days=window_days)).isoformat()

    query = text("""
        SELECT
            COUNT(*)                                                       AS total_approved,
            COUNT(*) FILTER (WHERE o.outcome_type = 'ACCOUNT_DEFAULT')    AS defaults
        FROM decisions d
        LEFT JOIN decision_outcomes o
            ON o.correlation_id = d.correlation_id
        WHERE d.recommendation = 'APPROVE'
          AND d.created_at >= :cutoff
    """)

    async with get_session() as session:
        row = (await session.execute(query, {"cutoff": cutoff})).fetchone()

    total    = row.total_approved if row else 0
    defaults = row.defaults       if row else 0
    rate     = defaults / max(total, 1)
    return rate


async def run_drift_check(threshold: float, window_days: int = 30) -> dict:
    rate = await compute_rolling_default_rate(window_days)
    DEFAULT_RATE_GAUGE.labels(window_days=str(window_days)).set(rate)

    breached = rate > threshold
    if breached:
        DRIFT_ALERTS.labels(window_days=str(window_days)).inc()
        logger.warning(
            "model_drift_detected",
            default_rate=round(rate, 4),
            threshold=threshold,
            window_days=window_days,
        )
    else:
        logger.info(
            "drift_check_ok",
            default_rate=round(rate, 4),
            threshold=threshold,
            window_days=window_days,
        )

    return {"default_rate": rate, "threshold": threshold, "breached": breached, "window_days": window_days}


async def run_drift_loop(threshold: float, interval_seconds: int = 3600) -> None:
    """Periodic drift check — run as an asyncio background task."""
    while True:
        try:
            await run_drift_check(threshold)
        except Exception as exc:
            logger.error("drift_check_error", error_type=type(exc).__name__)
        await asyncio.sleep(interval_seconds)
