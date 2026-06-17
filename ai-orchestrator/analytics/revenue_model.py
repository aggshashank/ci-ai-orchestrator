"""
Revenue impact model.

Estimates the revenue impact of changing from one strategy version to another
based on the change in approval rate applied to estimated customer lifetime value.

Model assumptions (configurable via settings):
  revenue_rate   = 2.0%  — annual revenue as % of CLV
  avg_clv        = 2500  — default if not available from customer profiles
  avg_loan_size  = 5000  — average credit line per approved customer

The model is intentionally simple — its purpose is to give business analysts
a directional estimate, not a precise financial projection.
"""
from __future__ import annotations

import structlog
from sqlalchemy import text

from db.session import get_session

logger = structlog.get_logger()

# Configurable constants
_REVENUE_RATE   = 0.02    # 2% of CLV per year
_DEFAULT_CLV    = 2500.0  # USD — fallback when no customer profile exists
_MONTHS         = 12      # projection horizon


async def revenue_impact(from_version: str, to_version: str) -> dict:
    """
    Compare the approval rates of two strategy versions and estimate the
    revenue delta from switching from_version → to_version.

    Returns:
      {
        from_version, to_version,
        from_approval_rate, to_approval_rate,
        from_volume, to_volume,
        approval_rate_delta,
        projected_new_approvals,   # extra approvals per period if to_version is adopted
        estimated_revenue_impact,  # USD over projection_months
        projection_months,
        avg_clv_used,
        revenue_rate_used,
        note
      }
    """
    async with get_session() as session:
        # Approval rates for each strategy version
        row_from = (await session.execute(text("""
            SELECT
                COUNT(*)                                             AS total,
                COUNT(*) FILTER (WHERE recommendation='APPROVE')    AS approvals,
                AVG(COALESCE((customer_context_json->>'estimated_clv')::float, :default_clv)) AS avg_clv
            FROM decisions
            WHERE strategy_version = :version
        """), {"version": from_version, "default_clv": _DEFAULT_CLV})).fetchone()

        row_to = (await session.execute(text("""
            SELECT
                COUNT(*)                                             AS total,
                COUNT(*) FILTER (WHERE recommendation='APPROVE')    AS approvals,
                AVG(COALESCE((customer_context_json->>'estimated_clv')::float, :default_clv)) AS avg_clv
            FROM decisions
            WHERE strategy_version = :version
        """), {"version": to_version, "default_clv": _DEFAULT_CLV})).fetchone()

    from_total    = row_from.total    if row_from else 0
    from_approvals = row_from.approvals if row_from else 0
    to_total      = row_to.total      if row_to   else 0
    to_approvals  = row_to.approvals  if row_to   else 0

    from_rate = from_approvals / max(from_total, 1)
    to_rate   = to_approvals   / max(to_total,   1)

    avg_clv   = float(row_from.avg_clv or _DEFAULT_CLV) if row_from and row_from.avg_clv else _DEFAULT_CLV

    # Use from_version volume as the baseline for projection
    baseline_volume = from_total
    rate_delta      = to_rate - from_rate
    new_approvals   = round(rate_delta * baseline_volume)
    revenue_impact_ = round(new_approvals * avg_clv * _REVENUE_RATE * (_MONTHS / 12), 2)

    logger.info(
        "revenue_impact_computed",
        from_version=from_version,
        to_version=to_version,
        rate_delta=round(rate_delta, 4),
        projected_new_approvals=new_approvals,
        estimated_revenue_impact=revenue_impact_,
    )

    return {
        "from_version":              from_version,
        "to_version":                to_version,
        "from_approval_rate":        round(from_rate, 4),
        "to_approval_rate":          round(to_rate, 4),
        "from_volume":               from_total,
        "to_volume":                 to_total,
        "approval_rate_delta":       round(rate_delta, 4),
        "projected_new_approvals":   new_approvals,
        "estimated_revenue_impact":  revenue_impact_,
        "projection_months":         _MONTHS,
        "avg_clv_used":              avg_clv,
        "revenue_rate_used":         _REVENUE_RATE,
        "note": "Directional estimate only — assumes constant application volume",
    }
