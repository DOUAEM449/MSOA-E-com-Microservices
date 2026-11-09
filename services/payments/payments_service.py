import uuid
import os
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
    Returns (payment_dict, None) on success or (None, error_dict) on failure.
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

        conn.execute(
            """INSERT INTO payments (id, order_id, amount, method, status, created_at)
               VALUES (?, ?, ?, ?, 'SUCCESS', ?)""",
            (payment_id, order_id, amount, method, now),
        )
        conn.commit()

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
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            patch_resp = await client.patch(
                f"{ORDERS_URL}/api/orders/{order_id}/status",
                json={"status": "PAID"},
            )
        if patch_resp.status_code not in (200, 204):
            # Payment recorded but could not update order — log a warning
            print(f"[payments] WARNING: payment recorded but PATCH to PAID failed ({patch_resp.status_code})")
    except (httpx.ConnectError, httpx.TimeoutException):
        print(f"[payments] WARNING: payment recorded but Orders service unreachable for PATCH")

    return payment, None

