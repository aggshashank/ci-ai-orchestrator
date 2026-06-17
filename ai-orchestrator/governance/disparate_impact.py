"""
4/5ths (80%) rule disparate impact analysis.

The 4/5ths rule: if the selection (approval) rate for any group is less than
80% of the rate for the group with the highest rate, the difference is
considered evidence of adverse impact (EEOC Uniform Guidelines).

Segments analysed:
  - credit_tier  (derived from credit score bands stored in application_json)
  - channel      (WEB / MOBILE / BRANCH from application_json)

We do NOT store or analyse race/gender/national origin — those are Reg B
prohibited bases.  The proxy segments above allow monitoring for disparate
outcomes on neutral credit factors.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional

import structlog

logger = structlog.get_logger()


def _credit_tier(score: Optional[int]) -> str:
    if score is None:       return "UNKNOWN"
    if score < 580:         return "POOR"
    if score < 670:         return "FAIR"
    if score < 740:         return "GOOD"
    if score < 800:         return "VERY_GOOD"
    return "EXCEPTIONAL"


@dataclass
class SegmentResult:
    segment_name: str
    segment_value: str
    total_decisions: int
    approvals: int
    approval_rate: float
    ratio_to_best: float        # approval_rate / best_group_rate
    violation: bool             # ratio_to_best < threshold
    p_value: Optional[float] = None


@dataclass
class FairnessAnalysisResult:
    period_days: int
    total_decisions: int
    overall_approval_rate: float
    threshold: float            # 4/5ths = 0.8
    segments: list[SegmentResult] = field(default_factory=list)
    violations: list[SegmentResult] = field(default_factory=list)
    computed_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @property
    def has_violations(self) -> bool:
        return len(self.violations) > 0


async def run_analysis(period_days: int = 30, threshold: float = 0.8, min_segment_size: int = 30) -> FairnessAnalysisResult:
    """
    Pull decisions for the period, segment by credit_tier and channel,
    compute approval rates and 4/5ths ratios.
    """
    from db.session import get_session
    from sqlalchemy import text

    cutoff = (datetime.now(timezone.utc) - timedelta(days=period_days)).isoformat()

    query = text("""
        SELECT
            recommendation,
            application_json ->> 'channel'     AS channel,
            (application_json ->> 'creditScore')::int AS credit_score
        FROM decisions
        WHERE created_at >= :cutoff
          AND decision_type = 'ORIGINATION'
    """)

    async with get_session() as session:
        rows = (await session.execute(query, {"cutoff": cutoff})).fetchall()

    if not rows:
        return FairnessAnalysisResult(
            period_days=period_days,
            total_decisions=0,
            overall_approval_rate=0.0,
            threshold=threshold,
        )

    total     = len(rows)
    approvals = sum(1 for r in rows if r.recommendation == "APPROVE")
    overall   = approvals / total

    # ── Segment by channel ─────────────────────────────────────────────────
    channel_buckets: dict[str, list] = {}
    tier_buckets:    dict[str, list] = {}

    for row in rows:
        ch    = (row.channel or "UNKNOWN").upper()
        tier  = _credit_tier(row.credit_score)
        approved = row.recommendation == "APPROVE"

        channel_buckets.setdefault(ch,   []).append(approved)
        tier_buckets.setdefault(tier, []).append(approved)

    def _rate(lst: list) -> float:
        return sum(lst) / len(lst) if lst else 0.0

    def _build_segments(buckets: dict[str, list], segment_name: str) -> list[SegmentResult]:
        results = []
        rates = {k: _rate(v) for k, v in buckets.items() if len(v) >= min_segment_size}
        if not rates:
            return results
        best_rate = max(rates.values())
        for val, lst in buckets.items():
            if len(lst) < min_segment_size:
                continue
            rate = _rate(lst)
            ratio = rate / best_rate if best_rate > 0 else 1.0
            results.append(SegmentResult(
                segment_name=segment_name,
                segment_value=val,
                total_decisions=len(lst),
                approvals=sum(lst),
                approval_rate=round(rate, 4),
                ratio_to_best=round(ratio, 4),
                violation=ratio < threshold,
            ))
        return results

    segments = _build_segments(channel_buckets, "channel") + _build_segments(tier_buckets, "credit_tier")
    violations = [s for s in segments if s.violation]

    result = FairnessAnalysisResult(
        period_days=period_days,
        total_decisions=total,
        overall_approval_rate=round(overall, 4),
        threshold=threshold,
        segments=segments,
        violations=violations,
    )

    logger.info(
        "disparate_impact_analysis",
        total=total,
        violations=len(violations),
        period_days=period_days,
    )
    return result
