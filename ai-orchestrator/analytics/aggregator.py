"""
Decision analytics aggregator.

Provides SQL-backed aggregate queries over the decisions table for the
analytics dashboard.  All queries are read-only and use async SQLAlchemy.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

import structlog
from sqlalchemy import text

from db.session import get_session

logger = structlog.get_logger()


async def approval_rate_by_day(days: int = 30) -> list[dict]:
    """
    Returns daily approval rates as a time series.
    Each entry: { date, total, approvals, declines, manual_reviews, approval_rate }
    """
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    async with get_session() as session:
        rows = (await session.execute(text("""
            SELECT
                DATE(created_at)                                              AS date,
                COUNT(*)                                                      AS total,
                COUNT(*) FILTER (WHERE recommendation = 'APPROVE')           AS approvals,
                COUNT(*) FILTER (WHERE recommendation = 'DECLINE')           AS declines,
                COUNT(*) FILTER (WHERE recommendation = 'MANUAL_REVIEW')     AS manual_reviews
            FROM decisions
            WHERE created_at >= :cutoff
            GROUP BY DATE(created_at)
            ORDER BY date ASC
        """), {"cutoff": cutoff})).fetchall()

    return [
        {
            "date":           str(r.date),
            "total":          r.total,
            "approvals":      r.approvals,
            "declines":       r.declines,
            "manual_reviews": r.manual_reviews,
            "approval_rate":  round(r.approvals / max(r.total, 1), 4),
        }
        for r in rows
    ]


async def decisions_by_segment(days: int = 30) -> dict:
    """
    Breaks down decisions by channel and credit tier.
    """
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    async with get_session() as session:
        rows = (await session.execute(text("""
            SELECT
                application_json ->> 'channel'                   AS channel,
                CASE
                    WHEN (application_json ->> 'creditScore')::int < 580  THEN 'POOR'
                    WHEN (application_json ->> 'creditScore')::int < 670  THEN 'FAIR'
                    WHEN (application_json ->> 'creditScore')::int < 740  THEN 'GOOD'
                    WHEN (application_json ->> 'creditScore')::int < 800  THEN 'VERY_GOOD'
                    ELSE 'EXCEPTIONAL'
                END                                              AS credit_tier,
                recommendation,
                COUNT(*)                                         AS count
            FROM decisions
            WHERE created_at >= :cutoff
              AND decision_type = 'ORIGINATION'
            GROUP BY channel, credit_tier, recommendation
            ORDER BY channel, credit_tier, recommendation
        """), {"cutoff": cutoff})).fetchall()

    by_channel: dict = {}
    by_tier: dict = {}

    for r in rows:
        # Channel breakdown
        ch = r.channel or "UNKNOWN"
        by_channel.setdefault(ch, {"APPROVE": 0, "DECLINE": 0, "MANUAL_REVIEW": 0})
        if r.recommendation in by_channel[ch]:
            by_channel[ch][r.recommendation] += r.count

        # Credit tier breakdown
        tier = r.credit_tier or "UNKNOWN"
        by_tier.setdefault(tier, {"APPROVE": 0, "DECLINE": 0, "MANUAL_REVIEW": 0})
        if r.recommendation in by_tier[tier]:
            by_tier[tier][r.recommendation] += r.count

    # Compute approval rates
    def _add_rate(bucket: dict) -> dict:
        result = {}
        for k, v in bucket.items():
            total = sum(v.values())
            result[k] = {**v, "total": total,
                         "approval_rate": round(v["APPROVE"] / max(total, 1), 4)}
        return result

    return {
        "by_channel":     _add_rate(by_channel),
        "by_credit_tier": _add_rate(by_tier),
    }


async def strategy_performance(days: int = 90) -> list[dict]:
    """
    Per-strategy-version approval rates and average confidence.
    """
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    async with get_session() as session:
        rows = (await session.execute(text("""
            SELECT
                strategy_version,
                COUNT(*)                                                       AS total,
                COUNT(*) FILTER (WHERE recommendation = 'APPROVE')            AS approvals,
                COUNT(*) FILTER (WHERE recommendation = 'DECLINE')            AS declines,
                COUNT(*) FILTER (WHERE recommendation = 'MANUAL_REVIEW')      AS manual_reviews,
                ROUND(AVG(confidence)::numeric, 4)                            AS avg_confidence,
                ROUND(AVG(composite_score)::numeric, 4)                       AS avg_composite,
                MIN(created_at)                                               AS first_seen,
                MAX(created_at)                                               AS last_seen
            FROM decisions
            WHERE created_at >= :cutoff
            GROUP BY strategy_version
            ORDER BY first_seen ASC
        """), {"cutoff": cutoff})).fetchall()

    return [
        {
            "strategy_version": r.strategy_version,
            "total":            r.total,
            "approvals":        r.approvals,
            "declines":         r.declines,
            "manual_reviews":   r.manual_reviews,
            "approval_rate":    round(r.approvals / max(r.total, 1), 4),
            "avg_confidence":   float(r.avg_confidence or 0),
            "avg_composite":    float(r.avg_composite or 0),
            "first_seen":       r.first_seen.isoformat() if r.first_seen else None,
            "last_seen":        r.last_seen.isoformat()  if r.last_seen  else None,
        }
        for r in rows
    ]


async def confidence_distribution(days: int = 30, bins: int = 10) -> list[dict]:
    """
    Histogram of confidence scores — useful for detecting confidence drift.
    """
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    async with get_session() as session:
        rows = (await session.execute(text("""
            SELECT
                FLOOR(confidence * :bins) / :bins   AS bucket_start,
                COUNT(*)                             AS count
            FROM decisions
            WHERE created_at >= :cutoff
            GROUP BY bucket_start
            ORDER BY bucket_start
        """), {"cutoff": cutoff, "bins": bins})).fetchall()

    return [
        {
            "bucket":       f"{float(r.bucket_start):.1f}–{float(r.bucket_start) + 1/bins:.1f}",
            "bucket_start": float(r.bucket_start),
            "count":        r.count,
        }
        for r in rows
    ]
