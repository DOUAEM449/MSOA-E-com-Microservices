import uuid
import os
import sqlite3
from datetime import datetime, timezone

import httpx

from database import get_db

ORDERS_URL = os.environ.get("ORDERS_URL", "http://localhost:8084")
TIMEOUT = 5.0  # seconds


def _row_to_dict(row):
    """Convert a sqlite3.Row to a camelCase dict."""
    return {
        "id": row["id"],
        "orderId": row["order_id"],
        "amount": row["amount"],
        "method": row["method"],
        "status": row["status"],
        "createdAt": row["created_at"],
    }


def list_payments():
    """Return all payments."""
    conn = get_db()
    try:
        rows = conn.execute("SELECT * FROM payments ORDER BY created_at DESC").fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        conn.close()


def get_payment_by_order(order_id: str):
    """Return the payment for a given order, or None."""
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT * FROM payments WHERE order_id = ?", (order_id,)
        ).fetchone()
        return _row_to_dict(row) if row else None
    finally:
        conn.close()


async def create_payment(order_id: str, method: str):
    """
    Create a payment for the given order.
    1. Fetch the order from Orders service (must be PENDING_PAYMENT).
    2. Record the payment locally.
    3. PATCH the order status to PAID.
       If that fails, the payment is deleted again (compensation),
       so a payment never exists for an order that is not PAID.
    Returns (payment_dict, None) on success or (None, error_dict) on failure.
    """

    # --- 1. Fetch the order from Orders service ---
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.get(f"{ORDERS_URL}/api/orders/{order_id}")
    except httpx.TransportError:
        return None, (503, {"message": "Orders service is unavailable"})

    if resp.status_code == 404:
        return None, (404, {"message": f"Order {order_id} not found"})
    if resp.status_code != 200:
        return None, (502, {"message": "Unexpected response from Orders service"})

    order = resp.json()

    # --- 2. Verify the order is PENDING_PAYMENT ---
    if order.get("status") != "PENDING_PAYMENT":
        return None, (
            409,
            {"message": f"Order {order_id} is not pending payment (current: {order.get('status')})"},
        )

    # --- 3. Check for duplicate payment ---
    conn = get_db()
    try:
        existing = conn.execute(
            "SELECT id FROM payments WHERE order_id = ?", (order_id,)
        ).fetchone()
        if existing:
            return None, (409, {"message": f"Payment already exists for order {order_id}"})

        # --- 4. Insert the payment ---
        payment_id = f"payment-{uuid.uuid4().hex[:8]}"
        amount = order["total"]
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        try:
            conn.execute(
                """INSERT INTO payments (id, order_id, amount, method, status, created_at)
                   VALUES (?, ?, ?, ?, 'SUCCESS', ?)""",
                (payment_id, order_id, amount, method, now),
            )
            conn.commit()
        except sqlite3.IntegrityError:
            # Another request paid this order at the same moment (order_id is UNIQUE).
            return None, (409, {"message": f"Payment already exists for order {order_id}"})

        payment = {
            "id": payment_id,
            "orderId": order_id,
            "amount": amount,
            "method": method,
            "status": "SUCCESS",
            "createdAt": now,
        }
    finally:
        conn.close()

    # --- 5. PATCH the order status to PAID ---
    error = await _mark_order_paid(order_id)
    if error:
        # Compensation: the order is not PAID, so the payment must not stay recorded.
        _delete_payment(payment_id)
        print(f"[payments] PATCH to PAID failed for {order_id}, payment {payment_id} rolled back")
        return None, error

    return payment, None


async def _mark_order_paid(order_id: str):
    """PATCH the order to PAID. Returns None on success, or (status_code, body) on failure."""
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.patch(
                f"{ORDERS_URL}/api/orders/{order_id}/status",
                json={"status": "PAID"},
            )
    except httpx.TransportError:
        return 503, {"message": "Orders service is unavailable, payment was not recorded"}

    if resp.status_code in (200, 204):
        return None
    if resp.status_code == 409:
        # e.g. the order was cancelled between our GET and this PATCH
        return 409, {"message": f"Order {order_id} can no longer be paid"}
    return 502, {"message": "Orders service could not mark the order as PAID, payment was not recorded"}


def _delete_payment(payment_id: str):
    conn = get_db()
    try:
        conn.execute("DELETE FROM payments WHERE id = ?", (payment_id,))
        conn.commit()
    finally:
        conn.close()

