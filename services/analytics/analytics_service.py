import json

from database import get_db


def get_summary():
    with get_db() as conn:
        total = conn.execute(
            "SELECT COUNT(*) FROM events"
        ).fetchone()[0]

        by_type = conn.execute("""
            SELECT event_type, COUNT(*) AS count
            FROM events
            GROUP BY event_type
        """).fetchall()

        by_source = conn.execute("""
            SELECT source, COUNT(*) AS count
            FROM events
            GROUP BY source
        """).fetchall()

        orders_count = conn.execute("""
            SELECT COUNT(DISTINCT order_id)
            FROM events
        """).fetchone()[0]

    return {
        "totalEvents": total,
        "totalOrdersTracked": orders_count,
        "eventsByType": {
            row["event_type"]: row["count"] for row in by_type
        },
        "eventsBySource": {
            row["source"]: row["count"] for row in by_source
        }
    }


def get_events(limit=100, offset=0, event_type=None):
    with get_db() as conn:
        if event_type:
            rows = conn.execute("""
                SELECT * FROM events
                WHERE event_type = ?
                ORDER BY received_at DESC, event_id DESC
                LIMIT ? OFFSET ?
            """, (event_type, limit, offset)).fetchall()
        else:
            rows = conn.execute("""
                SELECT * FROM events
                ORDER BY received_at DESC, event_id DESC
                LIMIT ? OFFSET ?
            """, (limit, offset)).fetchall()

    return [{
        "eventId": row["event_id"],
        "eventType": row["event_type"],
        "source": row["source"],
        "occurredAt": row["occurred_at"],
        "orderId": row["order_id"],
        "data": json.loads(row["event_data"]),
        "receivedAt": row["received_at"]
    } for row in rows]
