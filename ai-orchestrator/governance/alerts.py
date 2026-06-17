"""
Fairness alert dispatcher.

Sends a P2 alert when the 4/5ths rule is violated.  Supports Slack webhook
and/or email (SMTP).  Both are optional — alert is always logged regardless.
"""
from __future__ import annotations

import json
import smtplib
from email.mime.text import MIMEText
from typing import Optional
from urllib import request as urllib_request

import structlog

from governance.disparate_impact import FairnessAnalysisResult

logger = structlog.get_logger()


def _send_slack(webhook_url: str, result: FairnessAnalysisResult) -> None:
    if not webhook_url:
        return
    violations_text = "\n".join(
        f"  • {v.segment_name}={v.segment_value}: ratio {v.ratio_to_best:.3f}"
        for v in result.violations
    )
    payload = {
        "text": (
            f":rotating_light: *P2 Fairness Alert — {len(result.violations)} violation(s)* "
            f"({result.period_days}-day window, {result.total_decisions} decisions)\n"
            f"{violations_text}"
        )
    }
    data = json.dumps(payload).encode()
    req = urllib_request.Request(webhook_url, data=data,
                                 headers={"Content-Type": "application/json"})
    try:
        urllib_request.urlopen(req, timeout=10)
        logger.info("fairness_slack_alert_sent", violations=len(result.violations))
    except Exception as exc:
        logger.error("fairness_slack_alert_failed", error_type=type(exc).__name__)


def _send_email(to_addr: str, result: FairnessAnalysisResult, smtp_host: str = "localhost") -> None:
    if not to_addr:
        return
    body = (
        f"Fairness Monitor detected {len(result.violations)} disparate impact violation(s).\n\n"
        + "\n".join(
            f"  {v.segment_name}={v.segment_value}: approval rate {v.approval_rate:.1%}, "
            f"4/5ths ratio {v.ratio_to_best:.3f}"
            for v in result.violations
        )
    )
    msg = MIMEText(body)
    msg["Subject"] = f"[P2] Fairness Alert — {len(result.violations)} violation(s)"
    msg["From"]    = "ai-orchestrator@internal"
    msg["To"]      = to_addr

    try:
        with smtplib.SMTP(smtp_host, 25, timeout=10) as server:
            server.sendmail(msg["From"], [to_addr], msg.as_string())
        logger.info("fairness_email_alert_sent", to=to_addr)
    except Exception as exc:
        logger.error("fairness_email_alert_failed", error_type=type(exc).__name__)


def dispatch(
    result: FairnessAnalysisResult,
    slack_webhook: str = "",
    alert_email: str = "",
) -> None:
    """Always logs; optionally sends Slack + email."""
    if not result.has_violations:
        logger.info("fairness_check_clean", period_days=result.period_days)
        return

    logger.warning(
        "fairness_violations_detected",
        count=len(result.violations),
        period_days=result.period_days,
        segments=[f"{v.segment_name}={v.segment_value}" for v in result.violations],
    )

    _send_slack(slack_webhook, result)
    _send_email(alert_email, result)
