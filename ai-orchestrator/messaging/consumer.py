"""
Kafka consumer for application.received events.
"""
import json
import threading

import structlog
from kafka import KafkaConsumer

from config import get_settings
from experimentation.router import assign_variant
from graph.workflow import build_workflow
from logging_config import bind_correlation_id, clear_log_context
from messaging.dlq_producer import DlqProducer
from models.events import ApplicationReceivedEvent

logger = structlog.get_logger()
_graph = None
_graph_lock = threading.Lock()


def get_graph():
    global _graph
    with _graph_lock:
        if _graph is None:
            logger.info("Building LangGraph workflow")
            _graph = build_workflow()
            logger.info("LangGraph workflow ready")
    return _graph


def start_consumer():
    settings = get_settings()
    dlq = DlqProducer()

    consumer = KafkaConsumer(
        settings.kafka_topic_application_received,
        bootstrap_servers=settings.kafka_bootstrap_servers,
        group_id=settings.kafka_group_id,
        auto_offset_reset="earliest",
        enable_auto_commit=False,
        value_deserializer=lambda b: json.loads(b.decode("utf-8")),
        consumer_timeout_ms=1000,
    )

    logger.info(
        "Kafka consumer started",
        topic=settings.kafka_topic_application_received,
        group=settings.kafka_group_id,
    )

    graph = get_graph()

    while True:
        try:
            for message in consumer:
                corr = "unknown"
                try:
                    event = ApplicationReceivedEvent(**message.value)
                    corr = event.correlationId
                    bind_correlation_id(corr)

                    logger.info(
                        "Event received",
                        correlation_id=corr,
                        offset=message.offset,
                    )

                    _settings = get_settings()
                    variant = ""
                    if _settings.experiment_enabled and _settings.experiment_challenger_strategy:
                        variant = assign_variant(corr, _settings.experiment_challenger_percentage)

                    state = {
                        "correlation_id": corr,
                        "application": event.application,
                        "experiment_variant": variant,
                        "prompt_versions": {},
                    }

                    result = graph.invoke(state)
                    recommendation = result.get("risk_decision", {}).get("recommendation")

                    logger.info(
                        "Workflow complete",
                        correlation_id=corr,
                        recommendation=recommendation,
                    )
                    consumer.commit()

                except Exception as exc:
                    logger.error(
                        "Event processing failed - routing to DLQ",
                        correlation_id=corr,
                        error_type=type(exc).__name__,
                    )
                    dlq.send(message.value, error_type=type(exc).__name__)
                    consumer.commit()
                finally:
                    clear_log_context()

        except Exception as exc:
            logger.error("Consumer loop error", error_type=type(exc).__name__)
