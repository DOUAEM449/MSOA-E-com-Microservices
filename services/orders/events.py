import json
import logging
import os
from datetime import datetime, timezone
from uuid import uuid4

from confluent_kafka import Producer

logger = logging.getLogger(__name__)

_producer = None


def get_producer():
    """Create Kafka producer only once."""
    global _producer

    if _producer is None:
        config = {
            "bootstrap.servers": os.getenv(
                "KAFKA_BOOTSTRAP_SERVERS",
                "localhost:9092"
            ),
            "message.timeout.ms": 3000,
        }

        _producer = Producer(config)

    return _producer


def delivery_report(err, msg):
    """Report Kafka message delivery result."""
    if err is not None:
        logger.error("Kafka delivery failed: %s", err)
    else:
        logger.info(
            "Kafka message delivered: topic=%s partition=%s offset=%s",
            msg.topic(),
            msg.partition(),
            msg.offset(),
        )


def publish_event(event_type, source, order_id, data):
    """
    Publish an event to Kafka without waiting for broker delivery.
    Kafka errors must not block the REST request.
    """

    event = {
        "eventId": str(uuid4()),
        "eventType": event_type,
        "source": source,
        "occurredAt": datetime.now(timezone.utc).isoformat(
            timespec="milliseconds"
        ).replace("+00:00", "Z"),
        "orderId": str(order_id),
        "data": data,
    }

    try:
        producer = get_producer()

        producer.produce(
            topic=os.getenv(
                "KAFKA_TOPIC",
                "ecommerce-events"
            ),
            key=str(order_id),
            value=json.dumps(event, ensure_ascii=False),
            callback=delivery_report,
        )

        producer.poll(0)

        logger.info(
            "Kafka event queued: %s | orderId=%s",
            event_type,
            order_id,
        )

    except Exception:
        logger.warning(
            "Could not publish Kafka event %s for order %s",
            event_type,
            order_id,
            exc_info=True,
        )


def close_producer():
    """Flush pending Kafka messages when the application shuts down."""
    global _producer

    if _producer is not None:
        try:
            remaining = _producer.flush(5)

            if remaining:
                logger.warning(
                    "%s Kafka message(s) were not delivered before shutdown",
                    remaining,
                )
            else:
                logger.info("Kafka Producer closed successfully.")

        except Exception:
            logger.exception("Error while closing Kafka Producer")

        finally:
            _producer = None