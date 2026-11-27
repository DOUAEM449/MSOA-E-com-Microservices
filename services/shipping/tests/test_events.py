import json
import events
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


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
        "ShipmentCreated",
        "shipping",
        "order-123",
        {"shipmentId": "shipment-1"}
    )

    assert len(fake.messages) == 1
    message = fake.messages[0]
    payload = json.loads(message["value"])

    assert message["topic"] == events.KAFKA_TOPIC
    assert message["key"] == "order-123"
    assert payload["eventType"] == "ShipmentCreated"
    assert payload["source"] == "shipping"
    assert payload["orderId"] == "order-123"
    assert payload["data"] == {"shipmentId": "shipment-1"}
    assert payload["eventId"]
    assert payload["occurredAt"].endswith("Z")
    assert fake.polled == [0]

    events.close_producer()


def test_kafka_failure_does_not_raise_exception(monkeypatch):
    def failing_producer(config):
        raise RuntimeError("Kafka is unavailable")

    monkeypatch.setattr(events, "Producer", failing_producer)
    monkeypatch.setattr(events, "_producer", None)

    events.publish_event(
        "ShipmentCreated",
        "shipping",
        "order-456",
        {}
    )


def test_close_producer_flushes_messages(monkeypatch):
    fake = FakeProducer({})
    monkeypatch.setattr(events, "_producer", fake)

    events.close_producer()

    assert events._producer is None


def test_http_create_shipment_succeeds_when_kafka_is_down(
    monkeypatch, tmp_path
):
    import sys
    from pathlib import Path
    from fastapi.testclient import TestClient
    import httpx

    service_dir = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(service_dir))

    import database
    import main
    import service

    # Use a temporary database
    db_path = tmp_path / "shipping_test.db"
    monkeypatch.setattr(database, "DB_PATH", db_path)

    # Initialize the database
    database.init_db()

    # Mock Orders service
    def mock_orders(request):
        return httpx.Response(
            200,
            json={
                "id": "order-test-123",
                "status": "PAID",
            },
        )

    monkeypatch.setattr(
        service,
        "ORDERS_URL",
        "http://orders.test",
    )

    # Make Kafka unavailable
    def failing_producer(config):
        raise RuntimeError("Kafka is unavailable")

    monkeypatch.setattr(events, "Producer", failing_producer)
    monkeypatch.setattr(events, "_producer", None)

    # Replace outbound HTTP client transport
    original_client = httpx.AsyncClient

    def mocked_client(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(mock_orders)
        return original_client(*args, **kwargs)

    monkeypatch.setattr(service.httpx, "AsyncClient", mocked_client)

    with TestClient(main.app) as client:
        response = client.post(
            "/api/shipments",
            json={
                "orderId": "order-test-123",
                "address": {
                    "name": "Test Customer",
                    "address": "Test Street",
                    "city": "Casablanca",
                },
            },
        )

    assert response.status_code in (200, 201)
    assert response.json()["orderId"] == "order-test-123"
    assert response.json()["status"] == "PREPARING"
