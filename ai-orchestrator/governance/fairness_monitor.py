"""
Fairness monitor — orchestrates the monthly disparate impact run.

Entry points:
  1. CLI:      python -m governance.fairness_monitor
  2. HTTP:     POST /api/v1/governance/fairness/run  (triggers via main.py)
  3. Async fn: run_fairness_check() — called by the API handler
"""
from __future__ import annotations

import asyncio
import sys

import structlog

logger = structlog.get_logger()


async def run_fairness_check(
    period_days: int = 30,
    *,
    threshold: float | None = None,
    min_segment_size: int | None = None,
    slack_webhook: str = "",
    alert_email: str = "",
) -> dict:
    """
    Run the full fairness pipeline:
      analysis → HTML report → DB persist → alert dispatch
    Returns a summary dict suitable for the API response.
    """
    from config import get_settings
    from governance.alerts import dispatch
    from governance.disparate_impact import run_analysis
    from governance.report import generate

    settings = get_settings()
    _threshold        = threshold        if threshold        is not None else settings.fairness_disparate_impact_threshold
    _min_segment_size = min_segment_size if min_segment_size is not None else settings.fairness_min_segment_size
    _slack            = slack_webhook or settings.fairness_alert_slack_webhook
    _email            = alert_email   or settings.fairness_alert_email

    result = await run_analysis(
        period_days=period_days,
        threshold=_threshold,
        min_segment_size=_min_segment_size,
    )

    report_html = generate(result)

    # Persist to DB
    try:
        await _persist_report(result, report_html)
    except Exception as exc:
        logger.error("fairness_report_persist_failed", error_type=type(exc).__name__)

    # Alert
    dispatch(result, slack_webhook=_slack, alert_email=_email)

    return {
        "period_days":         result.period_days,
        "total_decisions":     result.total_decisions,
        "overall_approval_rate": result.overall_approval_rate,
        "threshold":           result.threshold,
        "segments_analysed":   len(result.segments),
        "violations_count":    len(result.violations),
        "segments": [
            {
                "segment_name":   s.segment_name,
                "segment_value":  s.segment_value,
                "total_decisions": s.total_decisions,
                "approval_rate":  s.approval_rate,
                "ratio_to_best":  s.ratio_to_best,
                "violation":      s.violation,
            }
            for s in result.segments
        ],
        "computed_at": result.computed_at,
    }


async def _persist_report(result, report_html: str) -> None:
    import json as _json
    from db.session import get_session
    from sqlalchemy import text

    segments_data = _json.dumps([
        {
            "segment_name":    s.segment_name,
            "segment_value":   s.segment_value,
            "total_decisions": s.total_decisions,
            "approval_rate":   s.approval_rate,
            "ratio_to_best":   s.ratio_to_best,
            "violation":       s.violation,
        }
        for s in result.segments
    ])

    async with get_session() as session:
        await session.execute(
            text("""
                INSERT INTO fairness_reports
                    (report_date, period_days, total_decisions, overall_approval_rate,
                     violations_count, violations_json, report_html)
                VALUES
                    (:report_date, :period_days, :total_decisions, :overall_approval_rate,
                     :violations_count, :violations_json::jsonb, :report_html)
            """),
            {
                "report_date":           result.computed_at[:10],
                "period_days":           result.period_days,
                "total_decisions":       result.total_decisions,
                "overall_approval_rate": result.overall_approval_rate,
                "violations_count":      len(result.violations),
                "violations_json":       segments_data,
                "report_html":           report_html,
            },
        )
        await session.commit()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Monthly fairness monitor")
    parser.add_argument("--period-days", type=int, default=30)
    args = parser.parse_args()

    result = asyncio.run(run_fairness_check(period_days=args.period_days))
    violations = result.get("violations", 0)
    print(f"Fairness check complete: {violations} violation(s)")
    sys.exit(1 if violations > 0 else 0)
