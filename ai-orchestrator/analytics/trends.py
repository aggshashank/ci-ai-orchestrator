"""
Time-series trend analytics.

Provides rolling-window metrics suitable for the analytics dashboard's
trend charts: approval rate, default rate, confidence percentiles.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import structlog
from sqlalchemy import text

from db.session import get_session

logger = structlog.get_logger()


async def rolling_approval_rate(window_days: int = 7, periods: int = 12) -> list[dict]:
    """
    Weekly rolling approval rate for the last `periods` weeks.
    Returns list of { period_end, approval_rate, total } for trend charts.
    """
    now = datetime.now(timezone.utc)
    results = []

    async with get_session() as session:
        for i in range(periods - 1, -1, -1):
            end   = now - timedelta(days=i * window_days)
            start = end - timedelta(days=window_days)

            row = (await session.execute(text("""
                SELECT
                    COUNT(*)                                             AS total,
                    COUNT(*) FILTER (WHERE recommendation = 'APPROVE') AS approvals
                FROM decisions
                WHERE created_at >= :start AND created_at < :end
            """), {"start": start.isoformat(), "end": end.isoformat()})).fetchone()

            total     = row.total     if row else 0
            approvals = row.approvals if row else 0

            results.append({
                "period_end":    end.strftime("%Y-%m-%d"),
                "total":         total,
                "approvals":     approvals,
                "approval_rate": round(approvals / max(total, 1), 4),
            })

    return results


async def rolling_default_rate(window_days: int = 30, periods: int = 6) -> list[dict]:
    """
    Monthly rolling default rate on APPROVE decisions.
    Requires outcome events — returns zeros if none recorded yet.
    """
    now = datetime.now(timezone.utc)
    results = []

    async with get_session() as session:
        for i in range(periods - 1, -1, -1):
            end   = now - timedelta(days=i * window_days)
            start = end - timedelta(days=window_days)

            row = (await session.execute(text("""
                SELECT
                    COUNT(DISTINCT d.correlation_id)                               AS approved,
                    COUNT(DISTINCT o.correlation_id)
                        FILTER (WHERE o.outcome_type = 'ACCOUNT_DEFAULT')          AS defaults
                FROM decisions d
                LEFT JOIN decision_outcomes o
                    ON o.correlation_id = d.correlation_id
                WHERE d.recommendation = 'APPROVE'
                  AND d.created_at >= :start AND d.created_at < :end
            """), {"start": start.isoformat(), "end": end.isoformat()})).fetchone()

            approved = row.approved if row else 0
            defaults = row.defaults if row else 0

            results.append({
                "period_end":    end.strftime("%Y-%m-%d"),
                "approved":      approved,
                "defaults":      defaults,
                "default_rate":  round(defaults / max(approved, 1), 4),
            })

    return results


async def decision_volume_by_type(days: int = 30) -> list[dict]:
    """Volume breakdown by decision_type."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    async with get_session() as session:
        rows = (await session.execute(text("""
            SELECT decision_type, COUNT(*) AS total
            FROM decisions
            WHERE created_at >= :cutoff
            GROUP BY decision_type
            ORDER BY total DESC
        """), {"cutoff": cutoff})).fetchall()

    return [{"decision_type": r.decision_type, "total": r.total} for r in rows]
