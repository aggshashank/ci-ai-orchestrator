import json
import structlog
from kafka import KafkaProducer
from config import get_settings

logger = structlog.get_logger()


class DlqProducer:
    def __init__(self):
        settings = get_settings()
        self.topic = settings.kafka_topic_dlq
        self.producer = KafkaProducer(
            bootstrap_servers=settings.kafka_bootstrap_servers,
            value_serializer=lambda v: json.dumps(v).encode("utf-8"),
        )

    def send(self, original_event: dict, error: str):
        payload = {**original_event, "_dlq_error": error}
        self.producer.send(self.topic, value=payload)
        self.producer.flush()
        logger.info("DLQ event published", topic=self.topic, error=error[:100])
