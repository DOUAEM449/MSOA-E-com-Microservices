import asyncio
import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

import httpx

import database
from consumer import ShipmentRetry, handle_delivery
from main import app


def message():
    return {
        "messageId": str(uuid4()),
        "type": "ShipmentRequested",
        "orderId": f"order-{uuid4().hex}",
        "paymentId": f"payment-{uuid4().hex}",
        "address": {"name": "Test recipient", "address": "12 Test Street", "city": "Rabat"},
        "occurredAt": "2026-11-24T10:15:00Z",
    }


def init_database(path):
    schema = Path(database.__file__).parent / "db" / "schema.sql"
    with closing(sqlite3.connect(path)) as connection:
        connection.executescript(schema.read_text(encoding="utf-8"))


class ShippingTests(unittest.TestCase):
    def setUp(self):
        folder = self.enterContext(tempfile.TemporaryDirectory())
        self.path = Path(folder) / "shipping.db"
        init_database(self.path)
        self.enterContext(patch.object(database, "DB_PATH", self.path))
        self.orders = self.enterContext(patch("shipping_service._fetch_order", new_callable=AsyncMock))
        self.orders.return_value = ({"status": "PAID"}, None)
        self.kafka = self.enterContext(patch("shipping_service.publish_event"))
        self.message = message()
        self.channel = Mock()
        self.delivery = SimpleNamespace(delivery_tag=1, redelivered=False)

    def count(self):
        with closing(database.get_db()) as connection:
            return connection.execute(
                "SELECT count(*) FROM shipments WHERE order_id = ?", (self.message["orderId"],)
            ).fetchone()[0]

    def deliver(self, body):
        handle_delivery(self.channel, self.delivery, None, body)

    def test_invalid_delivery_is_rejected_without_requeue(self):
        for body in (
            b"{", b"{}",
            json.dumps(dict(self.message, messageId="not-a-uuid")).encode(),
            json.dumps(dict(self.message, occurredAt="2026-11-24T10:15:00+01:00")).encode(),
            json.dumps(dict(self.message, type="OtherEvent")).encode(),
            json.dumps(dict(self.message, address={"name": " ", "city": "Rabat"})).encode(),
        ):
            with self.subTest(body=body):
                self.channel.reset_mock()
                self.deliver(body)
                self.channel.basic_nack.assert_called_once_with(delivery_tag=1, requeue=False)
                self.channel.basic_ack.assert_not_called()
        self.orders.assert_not_called()
        self.assertEqual(self.count(), 0)

    def test_duplicate_is_acknowledged_even_if_orders_is_unavailable(self):
        body = json.dumps(self.message).encode()
        self.channel.basic_ack.side_effect = lambda **kwargs: self.assertEqual(self.count(), 1)
        self.deliver(body)
        self.orders.return_value = (None, (503, {"message": "Orders unavailable"}))
        self.delivery.redelivered = True
        self.deliver(body)
        self.assertEqual(self.channel.basic_ack.call_count, 2)
        self.orders.assert_awaited_once()
        self.kafka.assert_called_once()

    def test_orders_failure_leaves_delivery_unacked(self):
        self.orders.return_value = (None, (503, {"message": "Orders unavailable"}))
        with self.assertRaises(ShipmentRetry):
            self.deliver(json.dumps(self.message).encode())
        self.channel.basic_ack.assert_not_called()
        self.channel.basic_nack.assert_not_called()
        self.assertEqual(self.count(), 0)

    def test_sqlite_failure_leaves_delivery_unacked(self):
        with patch("shipping_service._save_shipment", side_effect=sqlite3.OperationalError("locked")):
            with self.assertRaises(sqlite3.OperationalError):
                self.deliver(json.dumps(self.message).encode())
        self.channel.basic_ack.assert_not_called()
        self.channel.basic_nack.assert_not_called()
        self.assertEqual(self.count(), 0)

    def test_http_health_during_consumer_lifespan(self):
        async def exercise():
            with patch("main.ShippingConsumer") as consumer_class:
                async with app.router.lifespan_context(app):
                    consumer_class.return_value.start.assert_called_once()
                    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
                        self.assertEqual((await client.get("/health")).json(), {"status": "UP"})
                consumer_class.return_value.stop.assert_called_once()

        asyncio.run(exercise())

    def test_concurrent_posts_and_retry_return_the_same_shipment(self):
        async def exercise():
            arrived = 0
            both_arrived = asyncio.Event()

            async def paid_order(order_id):
                nonlocal arrived
                arrived += 1
                if arrived == 2:
                    both_arrived.set()
                await asyncio.wait_for(both_arrived.wait(), timeout=5)
                return {"status": "PAID"}, None

            self.orders.side_effect = paid_order
            body = {key: self.message[key] for key in ("orderId", "address")}
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
                first, second = await asyncio.gather(
                    client.post("/api/shipments", json=body),
                    client.post("/api/shipments", json=body),
                )
                self.orders.side_effect = AssertionError("Duplicate should not call Orders")
                with closing(database.get_db()) as connection, connection:
                    connection.execute(
                        "UPDATE shipments SET status = 'SHIPPED' WHERE order_id = ?",
                        (self.message["orderId"],),
                    )
                repeated = await client.post("/api/shipments", json=body)
            self.assertEqual(sorted((first.status_code, second.status_code)), [200, 201])
            self.assertEqual(repeated.status_code, 200)
            self.assertEqual(first.json(), second.json())
            self.assertEqual(repeated.json(), dict(first.json(), status="SHIPPED"))

        asyncio.run(exercise())
        self.assertEqual(self.count(), 1)
        self.kafka.assert_called_once()
