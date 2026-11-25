import json
import os
import sqlite3

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_DIR = os.path.join(BASE_DIR, "db")
DB_PATH = os.path.join(DB_DIR, "analytics.db")


def get_db():
    os.makedirs(DB_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS events (
                event_id TEXT PRIMARY KEY,
                event_type TEXT NOT NULL,
                source TEXT NOT NULL,
                occurred_at TEXT NOT NULL,
                order_id TEXT NOT NULL,
                event_data TEXT NOT NULL,
                raw_event TEXT NOT NULL,
                received_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_events_order_id
            ON events(order_id)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_events_type
            ON events(event_type)
        """)
        conn.commit()


def save_event(event):
    required = [
        "eventId", "eventType", "source",
        "occurredAt", "orderId", "data"
    ]

    if not isinstance(event, dict):
        raise ValueError("Event must be a JSON object")

    if not all(key in event for key in required):
        raise ValueError("Invalid event envelope")

    if not isinstance(event["data"], dict):
        raise ValueError("Event data must be an object")

    with get_db() as conn:
        cursor = conn.execute("""
            INSERT OR IGNORE INTO events (
                event_id, event_type, source,
                occurred_at, order_id, event_data, raw_event
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            event["eventId"],
            event["eventType"],
            event["source"],
            event["occurredAt"],
            event["orderId"],
            json.dumps(event["data"]),
            json.dumps(event)
        ))
        conn.commit()
        return cursor.rowcount == 1
