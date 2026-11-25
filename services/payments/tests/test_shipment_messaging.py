"""Lab 4 — Payments publishes ShipmentRequested to RabbitMQ after a successful payment."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from messaging import SHIPPING_QUEUE, ShipmentRequestPublisher, build_shipment_requested
from test_payments import ORDER_PENDING, FakePublisher, make_client


# ── Integration with POST /api/payments ─────────────────────────


def test_successful_payment_publishes_shipment_request(tmp_path: Path) -> None:
    publisher = FakePublisher()
    with make_client(tmp_path, publisher=publisher) as client:
        resp = client.post("/api/payments", json={"orderId": "order-001", "method": "CARD"})

    assert resp.status_code == 201
    payment = resp.json()
    assert len(publisher.messages) == 1
    message = publisher.messages[0]
    assert message["type"] == "ShipmentRequested"
    assert message["orderId"] == "order-001"
    assert message["paymentId"] == payment["id"]
    assert message["address"] == {"name": "Demo", "address": "123 Main", "city": "Casablanca"}
    assert message["messageId"]
    assert message["occurredAt"].endswith("Z")


def test_failed_patch_does_not_publish(tmp_path: Path) -> None:
    publisher = FakePublisher()
    with make_client(tmp_path, patch_status=500, publisher=publisher) as client:
        resp = client.post("/api/payments", json={"orderId": "order-001", "method": "CARD"})

    assert resp.status_code == 502
    assert publisher.messages == []


def test_order_not_pending_does_not_publish(tmp_path: Path) -> None:
    publisher = FakePublisher()
    order = {**ORDER_PENDING, "status": "PAID"}
    with make_client(tmp_path, order=order, publisher=publisher) as client:
        resp = client.post("/api/payments", json={"orderId": "order-001", "method": "CARD"})

    assert resp.status_code == 409
    assert publisher.messages == []


def test_rabbitmq_down_still_returns_201(tmp_path: Path) -> None:
    publisher = FakePublisher(result=False)
    with make_client(tmp_path, publisher=publisher) as client:
        resp = client.post("/api/payments", json={"orderId": "order-001", "method": "CARD"})
        stored = client.get("/api/payments/order/order-001")

    assert resp.status_code == 201
    assert stored.status_code == 200


def test_publisher_crash_still_returns_201(tmp_path: Path) -> None:
    publisher = FakePublisher(error=RuntimeError("boom"))
    with make_client(tmp_path, publisher=publisher) as client:
        resp = client.post("/api/payments", json={"orderId": "order-001", "method": "CARD"})

    assert resp.status_code == 201


def test_publisher_closed_on_shutdown(tmp_path: Path) -> None:
    publisher = FakePublisher()
    with make_client(tmp_path, publisher=publisher):
        pass
    assert publisher.closed


def test_build_message_without_customer() -> None:
    message = build_shipment_requested({}, {"id": "payment-1", "orderId": "order-9"})
    assert message["address"] == {"name": "", "address": "", "city": ""}
    assert message["orderId"] == "order-9"


# ── ShipmentRequestPublisher against a fake pika connection ─────


class FakeChannel:
    def __init__(self, fail_publish: int = 0) -> None:
        self.is_open = True
        self.declared = None
        self.confirms = False
        self.published = []
        self.fail_publish = fail_publish

    def queue_declare(self, **kwargs):
        self.declared = kwargs

    def confirm_delivery(self):
        self.confirms = True

    def basic_publish(self, **kwargs):
        if self.fail_publish:
            self.fail_publish -= 1
            self.is_open = False
            raise ConnectionError("stream lost")
        self.published.append(kwargs)


class FakeConnection:
    def __init__(self, channel: FakeChannel) -> None:
        self._channel = channel
        self.is_open = True
        self.closed = False

    def channel(self):
        return self._channel

    def close(self):
        self.closed = True
        self.is_open = False


def _publisher_with(channels):
    connections = []

    def factory(_url):
        connection = FakeConnection(channels.pop(0))
        connections.append(connection)
        return connection

    return ShipmentRequestPublisher(url="amqp://test", connection_factory=factory), connections


def _message():
    return build_shipment_requested(
        ORDER_PENDING, {"id": "payment-1", "orderId": ORDER_PENDING["id"]}
    )


def test_publisher_declares_durable_queue_and_sends_persistent_message() -> None:
    pytest.importorskip("pika")
    channel = FakeChannel()
    publisher, _ = _publisher_with([channel])

    assert publisher.publish(_message()) is True

    assert channel.declared == {
        "queue": SHIPPING_QUEUE, "durable": True, "exclusive": False, "auto_delete": False,
    }
    assert channel.confirms is True
    sent = channel.published[0]
    assert sent["exchange"] == ""
    assert sent["routing_key"] == SHIPPING_QUEUE
    assert sent["mandatory"] is True
    assert sent["properties"].delivery_mode == 2
    assert sent["properties"].content_type == "application/json"


def test_publisher_reuses_its_connection() -> None:
    pytest.importorskip("pika")
    channel = FakeChannel()
    publisher, connections = _publisher_with([channel])

    publisher.publish(_message())
    publisher.publish(_message())

    assert len(connections) == 1
    assert len(channel.published) == 2


def test_publisher_reconnects_once_after_lost_connection() -> None:
    pytest.importorskip("pika")
    broken, fresh = FakeChannel(fail_publish=1), FakeChannel()
    publisher, connections = _publisher_with([broken, fresh])

    assert publisher.publish(_message()) is True
    assert len(connections) == 2
    assert connections[0].closed
    assert len(fresh.published) == 1


def test_publisher_returns_false_when_broker_unreachable() -> None:
    def factory(_url):
        raise ConnectionRefusedError("no broker")

    publisher = ShipmentRequestPublisher(url="amqp://test", connection_factory=factory)
    assert publisher.publish(_message()) is False
