import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import events

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class FakeProducer:
    def __init__(self, config):
        self.config = config
        self.messages = []
        self.polled = []

    def produce(self, **kwargs):
        self.messages.append(kwargs)

    def poll(self, timeout):
        self.polled.append(timeout)

    def flush(self, timeout):
        return 0


def test_publish_event_builds_correct_envelope(monkeypatch):
    fake = FakeProducer({})
    monkeypatch.setattr(events, "Producer", lambda config: fake)
    monkeypatch.setattr(events, "_producer", None)

    events.publish_event(
        "OrderCreated",
        "orders",
        "order-123",
        {"total": 100}
    )

    assert len(fake.messages) == 1
    message = fake.messages[0]
    payload = json.loads(message["value"])

    assert message["topic"] == "ecommerce-events"
    assert message["key"] == "order-123"
    assert payload["eventType"] == "OrderCreated"
    assert payload["source"] == "orders"
    assert payload["orderId"] == "order-123"
    assert payload["data"] == {"total": 100}
    assert payload["eventId"]
    assert payload["occurredAt"].endswith("Z")
    assert fake.polled == [0]

    events.close_producer()


def test_publish_event_uses_configured_topic(monkeypatch):
    fake = FakeProducer({})
    monkeypatch.setattr(events, "Producer", lambda config: fake)
    monkeypatch.setattr(events, "_producer", None)
    monkeypatch.setenv("KAFKA_TOPIC", "test-events")

    events.publish_event("PaymentCompleted", "payments", "order-456", {})

    assert fake.messages[0]["topic"] == "test-events"

    events.close_producer()


def test_kafka_failure_does_not_raise_exception(monkeypatch):
    def failing_producer(config):
        raise RuntimeError("Kafka is unavailable")

    monkeypatch.setattr(events, "Producer", failing_producer)
    monkeypatch.setattr(events, "_producer", None)

    # The function must handle the Kafka error without raising it.
    events.publish_event(
        "OrderCreated",
        "orders",
        "order-789",
        {"total": 50}
    )


def test_close_producer_flushes_messages(monkeypatch):
    fake = FakeProducer({})
    monkeypatch.setattr(events, "_producer", fake)

    events.close_producer()

    assert events._producer is None

