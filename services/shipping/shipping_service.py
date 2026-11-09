import uuid
import os
import secrets
import string
from datetime import datetime, timezone

import httpx

from database import get_db

ORDERS_URL = os.environ.get("ORDERS_URL", "http://localhost:8084")
TIMEOUT = 5.0  # seconds

# Valid status transitions (current → allowed next)
VALID_TRANSITIONS = {
    "PREPARING": "SHIPPED",
    "SHIPPED": "IN_TRANSIT",
    "IN_TRANSIT": "DELIVERED",
}


def _generate_tracking_number():
    """Generate a unique tracking number like MSOA-7F3K2A."""
    chars = string.ascii_uppercase + string.digits
    code = "".join(secrets.choice(chars) for _ in range(6))
    return f"MSOA-{code}"


def _row_to_dict(row):
    """Convert a sqlite3.Row to a camelCase dict with nested address."""
    return {
        "id": row["id"],
        "orderId": row["order_id"],
        "address": {
            "name": row["recipient_name"],
            "address": row["address"],
            "city": row["city"],
        },
        "trackingNumber": row["tracking_number"],
        "status": row["status"],
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
    }


def list_shipments():
    """Return all shipments."""
    conn = get_db()
    try:
        rows = conn.execute("SELECT * FROM shipments ORDER BY created_at DESC").fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        conn.close()


def get_shipment_by_order(order_id: str):
    """Return the shipment for a given order, or None."""
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT * FROM shipments WHERE order_id = ?", (order_id,)
        ).fetchone()
        return _row_to_dict(row) if row else None
    finally:
        conn.close()


def get_shipment_by_id(shipment_id: str):
    """Return a shipment by its id, or None."""
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT * FROM shipments WHERE id = ?", (shipment_id,)
        ).fetchone()
        return _row_to_dict(row) if row else None
    finally:
        conn.close()


async def create_shipment(order_id: str, address: dict):
    """
    Create a shipment for the given order.
    1. Verify the order exists and is PAID.
    2. Check no shipment already exists for this order.
    3. Insert the shipment.
    Returns (shipment_dict, None) on success or (None, error_tuple) on failure.
    """

    # --- 1. Fetch the order from Orders service ---
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.get(f"{ORDERS_URL}/api/orders/{order_id}")
    except (httpx.ConnectError, httpx.TimeoutException):
        return None, (503, {"message": "Orders service is unavailable"})

    if resp.status_code == 404:
        return None, (404, {"message": f"Order {order_id} not found"})
    if resp.status_code != 200:
        return None, (502, {"message": "Unexpected response from Orders service"})

    order = resp.json()

    # --- 2. Verify the order is PAID ---
    if order.get("status") != "PAID":
        return None, (
            409,
            {"message": f"Order {order_id} is not paid (current: {order.get('status')})"},
        )

    # --- 3. Check for duplicate shipment ---
    conn = get_db()
    try:
        existing = conn.execute(
            "SELECT id FROM shipments WHERE order_id = ?", (order_id,)
        ).fetchone()
        if existing:
            return None, (409, {"message": f"Shipment already exists for order {order_id}"})

        # --- 4. Insert the shipment ---
        shipment_id = f"shipment-{uuid.uuid4().hex[:8]}"
        tracking = _generate_tracking_number()
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        conn.execute(
            """INSERT INTO shipments
               (id, order_id, recipient_name, address, city, tracking_number, status, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, 'PREPARING', ?, ?)""",
            (
                shipment_id,
                order_id,
                address["name"],
                address["address"],
                address["city"],
                tracking,
                now,
                now,
            ),
        )
        conn.commit()

        shipment = {
            "id": shipment_id,
            "orderId": order_id,
            "address": address,
            "trackingNumber": tracking,
            "status": "PREPARING",
            "createdAt": now,
            "updatedAt": now,
        }
    finally:
        conn.close()

    return shipment, None


def update_shipment_status(shipment_id: str, new_status: str):
    """
    Advance the shipment to the next status.
    Only sequential transitions are allowed: PREPARING → SHIPPED → IN_TRANSIT → DELIVERED.
    Returns (shipment_dict, None) on success or (None, error_tuple) on failure.
    """
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT * FROM shipments WHERE id = ?", (shipment_id,)
        ).fetchone()

        if not row:
            return None, (404, {"message": f"Shipment {shipment_id} not found"})

        current_status = row["status"]

        # Check if transition is valid
        expected_next = VALID_TRANSITIONS.get(current_status)
        if expected_next is None:
            return None, (
                409,
                {"message": f"Shipment is already {current_status}, no further transitions allowed"},
            )
        if new_status != expected_next:
            return None, (
                409,
                {"message": f"Cannot transition from {current_status} to {new_status}. Expected: {expected_next}"},
            )

        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        conn.execute(
            "UPDATE shipments SET status = ?, updated_at = ? WHERE id = ?",
            (new_status, now, shipment_id),
        )
        conn.commit()

        shipment = _row_to_dict(row)
        shipment["status"] = new_status
        shipment["updatedAt"] = now
        return shipment, None
    finally:
        conn.close()

