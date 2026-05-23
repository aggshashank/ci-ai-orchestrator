"""
Kafka Consumer
--------------
Consumes ApplicationReceivedEvent from application.received,
invokes the LangGraph workflow, routes MANUAL_REVIEW to Kafka.
"""
import json
import threading
import structlog
from kafka import KafkaConsumer
from kafka.errors import KafkaError
from models.events import ApplicationReceivedEvent
from graph.workflow import build_workflow
from messaging.dlq_producer import DlqProducer
from config import get_settings

logger = structlog.get_logger()
_graph = None
_graph_lock = threading.Lock()


def get_graph():
    global _graph
    with _graph_lock:
        if _graph is None:
            logger.info("Building LangGraph workflow...")
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
        enable_auto_commit=False,         # manual commit after successful processing
        value_deserializer=lambda b: json.loads(b.decode("utf-8")),
        consumer_timeout_ms=1000,         # poll timeout — keeps loop alive
    )

    logger.info("Kafka consumer started",
                topic=settings.kafka_topic_application_received,
                group=settings.kafka_group_id)

    graph = get_graph()

    while True:
        try:
            for message in consumer:
                corr = "unknown"
                try:
                    event = ApplicationReceivedEvent(**message.value)
                    corr = event.correlationId

                    logger.info("Event received",
                                correlation_id=corr,
                                channel=event.channel,
                                offset=message.offset)

                    state = {
                        "correlation_id": corr,
                        "application": event.application,
                    }

                    result = graph.invoke(state)
                    recommendation = result.get("risk_decision", {}).get("recommendation")

                    logger.info("Workflow complete",
                                correlation_id=corr,
                                recommendation=recommendation)

                    consumer.commit()

                except Exception as e:
                    logger.error("Event processing failed — routing to DLQ",
                                 correlation_id=corr, error=str(e))
                    dlq.send(message.value, error=str(e))
                    consumer.commit()   # commit to avoid reprocessing the broken event

        except Exception as outer:
            logger.error("Consumer loop error", error=str(outer))
