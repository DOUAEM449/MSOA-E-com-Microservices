import json
import logging
import os
import threading
import time

from confluent_kafka import Consumer, KafkaException, TopicPartition, OFFSET_BEGINNING

from database import save_event

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("analytics-consumer")

BOOTSTRAP_SERVERS = os.getenv(
    "KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"
)
TOPIC = os.getenv("KAFKA_TOPIC", "ecommerce-events")
GROUP_ID = "analytics-service"

_stop_event = threading.Event()
_replay_event = threading.Event()
_consumer_thread = None


def consume_events():
    consumer = Consumer({
        "bootstrap.servers": BOOTSTRAP_SERVERS,
        "group.id": GROUP_ID,
        "auto.offset.reset": "earliest",
        "enable.auto.commit": False
    })

    try:
        consumer.subscribe([TOPIC])
        logger.info("Subscribed to topic: %s", TOPIC)

        while not _stop_event.is_set():
            msg = consumer.poll(1.0)

            if msg is None:
                continue

            if msg.error():
                logger.error("Kafka error: %s", msg.error())
                continue

            if _replay_event.is_set():
                assignment = consumer.assignment()

                if assignment:
                    for partition in assignment:
                        consumer.seek(TopicPartition(
                            partition.topic,
                            partition.partition,
                            OFFSET_BEGINNING
                        ))

                    _replay_event.clear()
                    logger.info("Replay started from earliest offsets")
                    continue

            try:
                event = json.loads(msg.value().decode("utf-8"))
                inserted = save_event(event)

                if inserted:
                    logger.info(
                        "Event saved: %s | %s",
                        event["eventType"],
                        event["eventId"]
                    )
                else:
                    logger.info(
                        "Duplicate ignored: %s",
                        event["eventId"]
                    )

                consumer.commit(message=msg, asynchronous=False)

            except (ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
                logger.error("Invalid event: %s", exc)
                consumer.commit(message=msg, asynchronous=False)

            except Exception:
                logger.exception("Event processing failed")
                time.sleep(1)

    except KafkaException:
        logger.exception("Kafka consumer error")

    finally:
        consumer.close()
        logger.info("Kafka consumer stopped")


def start_consumer():
    global _consumer_thread

    if _consumer_thread and _consumer_thread.is_alive():
        return

    _stop_event.clear()
    _consumer_thread = threading.Thread(
        target=consume_events,
        daemon=True
    )
    _consumer_thread.start()


def stop_consumer():
    _stop_event.set()

    if _consumer_thread:
        _consumer_thread.join(timeout=10)


def request_replay():
    if not _consumer_thread or not _consumer_thread.is_alive():
        return False

    _replay_event.set()
    return True
