import json
import logging
import os
import uuid
from datetime import datetime, timezone

from confluent_kafka import Producer

logger = logging.getLogger("shipping.kafka")

KAFKA_BOOTSTRAP_SERVERS = os.environ.get(
    "KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"
)
KAFKA_TOPIC = os.environ.get("KAFKA_TOPIC", "ecommerce-events")

_producer = None


def _get_producer():
    """Create the Kafka producer once."""
    global _producer

    if _producer is None:
        _producer = Producer({
            "bootstrap.servers": KAFKA_BOOTSTRAP_SERVERS,
        })

    return _producer


def _delivery_report(err, message):
    """Log the result of Kafka message delivery."""
    if err is not None:
        logger.warning("Kafka delivery failed: %s", err)
    else:
        logger.info(
            "Kafka event delivered: topic=%s partition=%s",
            message.topic(),
            message.partition(),
        )


def publish_event(event_type: str, source: str, order_id: str, data: dict):
    """
    Publish an event without blocking the HTTP request.
    Kafka failures must not interrupt the Shipping service.
    """
    event = {
        "eventId": str(uuid.uuid4()),
        "eventType": event_type,
        "source": source,
        "occurredAt": datetime.now(timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z"),
        "orderId": order_id,
        "data": data,
    }

    try:
        producer = _get_producer()

        producer.produce(
            topic=KAFKA_TOPIC,
            key=order_id,
            value=json.dumps(event),
            callback=_delivery_report,
        )

        producer.poll(0)

    except Exception as exc:
        logger.warning(
            "Could not publish %s event to Kafka: %s",
            event_type,
            exc,
        )


def close_producer():
    """Flush pending messages when the service shuts down."""
    global _producer

    if _producer is not None:
        try:
            remaining = _producer.flush(5)

            if remaining:
                logger.warning(
                    "%s Kafka message(s) were not delivered before shutdown",
                    remaining,
                )
        except Exception as exc:
            logger.warning("Error while closing Kafka producer: %s", exc)
        finally:
            _producer = None
