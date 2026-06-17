"""
Feature store for adaptive learning.

Computes signal accuracy features by joining decision_outcomes with the
agent_outputs stored at decision time.  These features feed model_trainer.py
to derive updated synthesis weights.

Signal accuracy definition:
  - credit_signal_correct: True when credit_agent predicted HIGH risk AND the
    outcome was ACCOUNT_DEFAULT, OR predicted LOW risk AND no default.
  - fraud_signal_correct: True when fraud_agent predicted HIGH fraud AND outcome
    was FRAUD_CONFIRMED, OR predicted LOW fraud AND no fraud outcome.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional

import structlog

logger = structlog.get_logger()


@dataclass
class SignalAccuracyFeatures:
    window_days: int
    total_outcomes: int
    default_count: int
    fraud_count: int
    payoff_count: int
    credit_signal_correct: int
    credit_signal_total: int
    fraud_signal_correct: int
    fraud_signal_total: int
    computed_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @property
    def credit_accuracy(self) -> float:
        return self.credit_signal_correct / max(self.credit_signal_total, 1)

    @property
    def fraud_accuracy(self) -> float:
        return self.fraud_signal_correct / max(self.fraud_signal_total, 1)

    @property
    def default_rate(self) -> float:
        """Default rate on APPROVE decisions — key drift metric."""
        return self.default_count / max(self.total_outcomes, 1)


async def compute_signal_accuracy(window_days: int = 180) -> SignalAccuracyFeatures:
    """
    Join decision_outcomes with agent_outputs and compute signal accuracy.
    Only considers decisions where the original recommendation was APPROVE
    (since DECLINE outcomes are not observable in the same way).
    """
    from db.session import get_session
    from sqlalchemy import text

    cutoff = (datetime.now(timezone.utc) - timedelta(days=window_days)).isoformat()

    query = text("""
        SELECT
            o.outcome_type,
            ao.output_json ->> 'riskLevel'   AS credit_risk_level,
            ao_fraud.output_json ->> 'fraudRisk' AS fraud_risk_level
        FROM decision_outcomes o
        JOIN decisions d ON d.correlation_id = o.correlation_id
        LEFT JOIN agent_outputs ao
            ON ao.decision_id = d.id AND ao.agent_name = 'credit_agent'
        LEFT JOIN agent_outputs ao_fraud
            ON ao_fraud.decision_id = d.id AND ao_fraud.agent_name = 'fraud_agent'
        WHERE o.consumed_at >= :cutoff
          AND o.original_recommendation = 'APPROVE'
    """)

    async with get_session() as session:
        rows = (await session.execute(query, {"cutoff": cutoff})).fetchall()

    total = len(rows)
    defaults = sum(1 for r in rows if r.outcome_type == "ACCOUNT_DEFAULT")
    frauds   = sum(1 for r in rows if r.outcome_type == "FRAUD_CONFIRMED")
    payoffs  = sum(1 for r in rows if r.outcome_type == "EARLY_PAYOFF")

    # Credit signal accuracy: HIGH predicted → default happened; LOW → no default
    credit_correct = 0
    credit_total = 0
    fraud_correct = 0
    fraud_total = 0

    for row in rows:
        is_default = row.outcome_type == "ACCOUNT_DEFAULT"
        is_fraud   = row.outcome_type == "FRAUD_CONFIRMED"

        if row.credit_risk_level is not None:
            credit_total += 1
            predicted_high = row.credit_risk_level.upper() == "HIGH"
            if predicted_high == is_default:
                credit_correct += 1

        if row.fraud_risk_level is not None:
            fraud_total += 1
            predicted_high = row.fraud_risk_level.upper() == "HIGH"
            if predicted_high == is_fraud:
                fraud_correct += 1

    features = SignalAccuracyFeatures(
        window_days=window_days,
        total_outcomes=total,
        default_count=defaults,
        fraud_count=frauds,
        payoff_count=payoffs,
        credit_signal_correct=credit_correct,
        credit_signal_total=credit_total,
        fraud_signal_correct=fraud_correct,
        fraud_signal_total=fraud_total,
    )

    logger.info(
        "signal_accuracy_computed",
        window_days=window_days,
        total_outcomes=total,
        credit_accuracy=round(features.credit_accuracy, 4),
        fraud_accuracy=round(features.fraud_accuracy, 4),
        default_rate=round(features.default_rate, 4),
    )

    return features
