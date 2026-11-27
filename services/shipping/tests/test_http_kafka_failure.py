
import sys
import sqlite3
from pathlib import Path

import events
import shipping_service
import main

from fastapi.testclient import TestClient


# Ensure the Shipping service directory is available
SERVICE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVICE_DIR))


def test_create_shipment_succeeds_when_kafka_is_down(
    tmp_path, monkeypatch
):
    # 1. Create an isolated temporary SQLite database
    db_path = tmp_path / "shipping_test.db"

    connection = sqlite3.connect(db_path)
    connection.execute("""
        CREATE TABLE shipments (
            id TEXT PRIMARY KEY,
            order_id TEXT NOT NULL UNIQUE,
            recipient_name TEXT NOT NULL,
            address TEXT NOT NULL,
            city TEXT NOT NULL,
            tracking_number TEXT NOT NULL,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)
    connection.commit()
    connection.close()

    def temporary_get_db():
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    monkeypatch.setattr(
        shipping_service, "get_db", temporary_get_db
    )

    # 2. Simulate an existing PAID order
    async def fake_fetch_order(order_id):
        return {"id": order_id, "status": "PAID"}, None

    monkeypatch.setattr(
        shipping_service, "_fetch_order", fake_fetch_order
    )

    # 3. Simulate Kafka being unavailable
    def failing_producer(config):
        raise RuntimeError("Kafka is unavailable")

    monkeypatch.setattr(events, "Producer", failing_producer)
    monkeypatch.setattr(events, "_producer", None)

    # 4. Send the real HTTP request
    payload = {
        "orderId": "order-kafka-test",
        "address": {
            "name": "Test User",
            "address": "Test Street",
            "city": "Casablanca"
        }
    }

    with TestClient(main.app) as client:
        response = client.post("/api/shipments", json=payload)

    # 5. Verify that HTTP creation succeeds despite Kafka failure
    assert response.status_code == 201

    body = response.json()
    assert body["orderId"] == "order-kafka-test"
    assert body["status"] == "PREPARING"

    # 6. Verify that the shipment was actually saved
    conn = temporary_get_db()
    try:
        row = conn.execute(
            "SELECT * FROM shipments WHERE order_id = ?",
            ("order-kafka-test",)
        ).fetchone()

        assert row is not None
        assert row["status"] == "PREPARING"
    finally:
        conn.close()

    events._producer = None
