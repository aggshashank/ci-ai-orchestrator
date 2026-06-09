"""
ExperimentTracker: per-variant recommendation distribution from the DB.
Also updates Prometheus gauges so Grafana panels stay current.
"""
from __future__ import annotations

from typing import Any

import structlog
from prometheus_client import Gauge
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Decision

logger = structlog.get_logger()

# Prometheus gauges — one per (variant, recommendation) pair
_VARIANT_GAUGE = Gauge(
    "experiment_variant_decisions",
    "Live decisions by experiment variant and recommendation",
    ["variant", "recommendation"],
)


class ExperimentTracker:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def get_variant_stats(self) -> dict[str, dict[str, int]]:
        """
        Return per-variant recommendation distribution for all non-NULL experiment_variant rows.
        Shape: {"champion": {"APPROVE": N, ...}, "challenger": {"APPROVE": N, ...}}
        """
        stmt = (
            select(
                Decision.experiment_variant,
                Decision.recommendation,
                func.count().label("cnt"),
            )
            .where(Decision.experiment_variant.isnot(None))
            .group_by(Decision.experiment_variant, Decision.recommendation)
        )
        result = await self._s.execute(stmt)
        rows = result.all()

        stats: dict[str, dict[str, int]] = {}
        for variant, recommendation, cnt in rows:
            stats.setdefault(variant, {})[recommendation] = cnt
        return stats

    async def refresh_prometheus(self) -> None:
        """Update Prometheus gauges from the current DB state."""
        try:
            stats = await self.get_variant_stats()
            for variant, dist in stats.items():
                for rec, count in dist.items():
                    _VARIANT_GAUGE.labels(variant=variant, recommendation=rec).set(count)
        except Exception as exc:
            logger.warning("experiment_tracker_prometheus_refresh_failed", error=str(exc))


def _rates(dist: dict[str, int]) -> dict[str, float]:
    total = max(sum(dist.values()), 1)
    return {k: round(v / total, 4) for k, v in dist.items()}


def format_stats_response(stats: dict[str, dict[str, int]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for variant, dist in stats.items():
        out[variant] = {
            "total": sum(dist.values()),
            "distribution": dist,
            "rates": _rates(dist),
        }
    return out
