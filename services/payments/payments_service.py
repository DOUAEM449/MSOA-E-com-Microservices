
import uuid
import sqlite3
from datetime import datetime, timezone
from typing import Optional, Tuple

import httpx

from database import get_db, DatabasePath
from events import publish_event

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


def list_payments(database_path: DatabasePath) -> list:
    """Return all payments."""
    conn = get_db(database_path)
    try:
        rows = conn.execute(
            "SELECT * FROM payments ORDER BY created_at DESC"
        ).fetchall()
        return [_row_to_dict(row) for row in rows]
    finally:
        conn.close()


def get_payment_by_order(
    database_path: DatabasePath,
    order_id: str
) -> Optional[dict]:
    """Return the payment for a given order, or None."""
    conn = get_db(database_path)
    try:
        row = conn.execute(
            "SELECT * FROM payments WHERE order_id = ?",
            (order_id,)
        ).fetchone()
        return _row_to_dict(row) if row else None
    finally:
        conn.close()


async def create_payment(
    database_path: DatabasePath,
    http_client: httpx.AsyncClient,
    orders_url: str,
    order_id: str,
    method: str,
) -> Tuple[Optional[dict], Optional[Tuple[int, dict]]]:
    """
    Create a payment, update the order, then publish PaymentCompleted.
    """

    # 1. Fetch order
    try:
        resp = await http_client.get(
            f"{orders_url}/api/orders/{order_id}"
        )
    except httpx.TransportError:
        return None, (503, {"message": "Orders service is unavailable"})

    if resp.status_code == 404:
        return None, (404, {"message": f"Order {order_id} not found"})

    if resp.status_code != 200:
        return None, (
            502,
            {"message": "Unexpected response from Orders service"}
        )

    order = resp.json()

    # 2. Verify order status
    if order.get("status") != "PENDING_PAYMENT":
        return None, (
            409,
            {
                "message": (
                    f"Order {order_id} is not pending payment "
                    f"(current: {order.get('status')})"
                )
            },
        )

    # 3. Check duplicate payment
    conn = get_db(database_path)

    try:
        existing = conn.execute(
            "SELECT id FROM payments WHERE order_id = ?",
            (order_id,)
        ).fetchone()

        if existing:
            return None, (
                409,
                {"message": f"Payment already exists for order {order_id}"}
            )

        # 4. Save payment
        payment_id = f"payment-{uuid.uuid4().hex[:8]}"
        amount = order["total"]
        now = datetime.now(timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )

        try:
            conn.execute(
                """
                INSERT INTO payments
                (id, order_id, amount, method, status, created_at)
                VALUES (?, ?, ?, ?, 'SUCCESS', ?)
                """,
                (payment_id, order_id, amount, method, now),
            )
            conn.commit()

        except sqlite3.IntegrityError:
            return None, (
                409,
                {"message": f"Payment already exists for order {order_id}"}
            )

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

    # 5. Update order status to PAID
    error = await _mark_order_paid(
        http_client,
        orders_url,
        order_id
    )

    if error:
        # Compensation
        _delete_payment(database_path, payment_id)

        print(
            f"[payments] PATCH to PAID failed for {order_id}, "
            f"payment {payment_id} rolled back"
        )
        return None, error

    # 6. Publish PaymentCompleted after successful payment
    publish_event(
        event_type="PaymentCompleted",
        source="payments",
        order_id=order_id,
        data={
            "paymentId": payment_id,
            "amount": amount,
            "method": method,
        },
    )

    return payment, None


async def _mark_order_paid(
    http_client: httpx.AsyncClient,
    orders_url: str,
    order_id: str,
) -> Optional[Tuple[int, dict]]:
    """PATCH the order to PAID."""

    try:
        resp = await http_client.patch(
            f"{orders_url}/api/orders/{order_id}/status",
            json={"status": "PAID"},
        )

    except httpx.TransportError:
        return (
            503,
            {"message": "Orders service is unavailable, payment was not recorded"}
        )

    if resp.status_code in (200, 204):
        return None

    if resp.status_code == 409:
        return (
            409,
            {"message": f"Order {order_id} can no longer be paid"}
        )

    return (
        502,
        {
            "message": (
                "Orders service could not mark the order as PAID, "
                "payment was not recorded"
            )
        },
    )


def _delete_payment(
    database_path: DatabasePath,
    payment_id: str
) -> None:
    """Delete a payment during compensation."""

    conn = get_db(database_path)
    try:
        conn.execute(
            "DELETE FROM payments WHERE id = ?",
            (payment_id,)
        )
        conn.commit()
    finally:
        conn.close()
