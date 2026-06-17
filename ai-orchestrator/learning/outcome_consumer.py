"""
Outcome event consumer.

Listens on three Kafka topics and joins each outcome back to the original
decision in PostgreSQL.  The joined row drives signal accuracy computation
in feature_store.py and quarterly weight retraining in model_trainer.py.

Topics:
  outcome.account_default   — loan/card went to default
  outcome.fraud_confirmed   — fraud team confirmed a fraud case
  outcome.early_payoff      — account paid off early (low-risk signal)
"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone

import structlog
from kafka import KafkaConsumer

from config import get_settings

logger = structlog.get_logger()


async def _store_outcome(event: dict) -> None:
    """Persist an outcome event, joined to its original decision row."""
    from db.session import get_session

    async with get_session() as session:
        result = await session.execute(
            """
            INSERT INTO decision_outcomes
                (correlation_id, outcome_type, outcome_date, months_on_books,
                 original_recommendation, original_confidence, consumed_at)
            VALUES
                (:correlation_id, :outcome_type, :outcome_date, :months_on_books,
                 :original_recommendation, :original_confidence, :consumed_at)
            ON CONFLICT (correlation_id, outcome_type) DO NOTHING
            """,
            {
                "correlation_id":       event["correlationId"],
                "outcome_type":         event["outcomeType"],
                "outcome_date":         event["outcomeDate"],
                "months_on_books":      event.get("monthsOnBooks", 0),
                "original_recommendation": event.get("originalRecommendation", ""),
                "original_confidence":  event.get("originalConfidence", 0.0),
                "consumed_at":          datetime.now(timezone.utc).isoformat(),
            },
        )
        await session.commit()

    logger.info(
        "outcome_stored",
        correlation_id=event["correlationId"],
        outcome_type=event["outcomeType"],
    )


async def _run_consumer(settings) -> None:
    topics = [
        settings.kafka_topic_outcome_default,
        settings.kafka_topic_outcome_fraud,
        settings.kafka_topic_outcome_payoff,
    ]

    consumer = KafkaConsumer(
        *topics,
        bootstrap_servers=settings.kafka_bootstrap_servers,
        group_id=f"{settings.kafka_group_id}-outcomes",
        auto_offset_reset="earliest",
        enable_auto_commit=False,
        value_deserializer=lambda b: json.loads(b.decode("utf-8")),
        consumer_timeout_ms=1000,
    )

    logger.info("outcome_consumer started", topics=topics)

    while True:
        try:
            for message in consumer:
                try:
                    await _store_outcome(message.value)
                    consumer.commit()
                except Exception as exc:
                    logger.error(
                        "outcome_event_failed",
                        error_type=type(exc).__name__,
                        topic=message.topic,
                    )
                    consumer.commit()
        except Exception as exc:
            logger.error("outcome_consumer loop error", error_type=type(exc).__name__)


def start_outcome_consumer() -> None:
    """Entry point — runs in its own daemon thread with its own event loop."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(_run_consumer(get_settings()))
