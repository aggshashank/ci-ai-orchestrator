"""
Kafka consumer — subscribes to all four workflow topics and routes each event
to the correct LangGraph workflow via WorkflowRouter.

Task 3.5: Runs its own asyncio event loop.  Each message dispatches
graph.ainvoke() which drives async agent functions — the LLM blocking
I/O is offloaded via asyncio.to_thread() inside each agent, keeping
the event loop responsive.

Topic → decision_type mapping:
  application.received              → ORIGINATION
  limit.review.triggered            → LIMIT_REVIEW
  delinquency.treatment.triggered   → DELINQUENCY_TREATMENT
  cross_sell.eligible               → CROSS_SELL
"""
from __future__ import annotations

import asyncio
import json

import structlog
from kafka import KafkaConsumer

from config import get_settings
from experimentation.router import assign_variant
from logging_config import bind_correlation_id, clear_log_context
from messaging.dlq_producer import DlqProducer
from models.events import (
    ApplicationReceivedEvent,
    CrossSellEvent,
    DelinquencyTreatmentEvent,
    LimitReviewTriggeredEvent,
)
from workflows.router import get_workflow

logger = structlog.get_logger()


def _build_state(topic: str, message_value: dict, settings) -> dict:
    """Deserialise the Kafka payload and build the initial GraphState dict."""
    decision_type = _topic_to_decision_type(topic, settings)
    corr = message_value.get("correlationId", "unknown")

    variant = ""
    if settings.experiment_enabled and settings.experiment_challenger_strategy:
        variant = assign_variant(corr, settings.experiment_challenger_percentage)

    base = {
        "correlation_id":   corr,
        "decision_type":    decision_type,
        "experiment_variant": variant,
        "prompt_versions":  {},
    }

    if decision_type == "ORIGINATION":
        event = ApplicationReceivedEvent(**message_value)
        cid = getattr(event.application, "customerId", None)
        return {**base, "application": event.application, "customer_id": cid or ""}

    if decision_type == "LIMIT_REVIEW":
        event = LimitReviewTriggeredEvent(**message_value)
        return {**base, "customer_id": event.customerId,
                "limit_review_request": event.request.model_dump()}

    if decision_type == "DELINQUENCY_TREATMENT":
        event = DelinquencyTreatmentEvent(**message_value)
        return {**base, "customer_id": event.customerId,
                "delinquency_request": event.request.model_dump()}

    if decision_type == "CROSS_SELL":
        event = CrossSellEvent(**message_value)
        return {**base, "customer_id": event.customerId,
                "cross_sell_request": event.request.model_dump()}

    raise ValueError(f"Unroutable decision_type: {decision_type!r}")


def _topic_to_decision_type(topic: str, settings) -> str:
    mapping = {
        settings.kafka_topic_application_received:  "ORIGINATION",
        settings.kafka_topic_limit_review:          "LIMIT_REVIEW",
        settings.kafka_topic_delinquency_treatment: "DELINQUENCY_TREATMENT",
        settings.kafka_topic_cross_sell:            "CROSS_SELL",
    }
    return mapping.get(topic, "ORIGINATION")


async def _process_message(message, settings, dlq: DlqProducer) -> None:
    """Async handler for a single Kafka message."""
    corr = "unknown"
    try:
        state = _build_state(message.topic, message.value, settings)
        corr  = state["correlation_id"]
        bind_correlation_id(corr)

        logger.info(
            "Event received",
            correlation_id=corr,
            topic=message.topic,
            decision_type=state["decision_type"],
            offset=message.offset,
        )

        graph  = get_workflow(state["decision_type"])
        result = await graph.ainvoke(state)   # async — agents use asyncio.to_thread for LLM
        recommendation = result.get("risk_decision", {}).get("recommendation")

        logger.info(
            "Workflow complete",
            correlation_id=corr,
            decision_type=state["decision_type"],
            recommendation=recommendation,
        )

    except Exception as exc:
        logger.error(
            "Event processing failed - routing to DLQ",
            correlation_id=corr,
            error_type=type(exc).__name__,
        )
        dlq.send(message.value, error_type=type(exc).__name__)
    finally:
        clear_log_context()


async def _consumer_loop(settings) -> None:
    """Async consumer loop — kafka polling is sync but message processing is async."""
    dlq = DlqProducer()
    topics = [
        settings.kafka_topic_application_received,
        settings.kafka_topic_limit_review,
        settings.kafka_topic_delinquency_treatment,
        settings.kafka_topic_cross_sell,
    ]

    consumer = KafkaConsumer(
        *topics,
        bootstrap_servers=settings.kafka_bootstrap_servers,
        group_id=settings.kafka_group_id,
        auto_offset_reset="earliest",
        enable_auto_commit=False,
        value_deserializer=lambda b: json.loads(b.decode("utf-8")),
        consumer_timeout_ms=1000,
    )

    logger.info("Kafka consumer started", topics=topics, group=settings.kafka_group_id)

    while True:
        try:
            for message in consumer:
                await _process_message(message, settings, dlq)
                consumer.commit()
        except Exception as exc:
            logger.error("Consumer loop error", error_type=type(exc).__name__)


def start_consumer() -> None:
    """
    Entry point — runs in its own daemon thread with a dedicated asyncio
    event loop so it does not contend with the FastAPI event loop.
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(_consumer_loop(get_settings()))
