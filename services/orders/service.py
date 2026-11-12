import asyncio
import logging
import math
import sqlite3
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

import httpx
from fastapi import HTTPException

from database import DatabasePath, get_connection
from schemas import CreateOrderInput, OrderStatus


logger = logging.getLogger(__name__)

STATUS_TRANSITIONS = {
    OrderStatus.PENDING_PAYMENT: {OrderStatus.PAID},
    OrderStatus.PAID: {OrderStatus.SHIPPED},
    OrderStatus.SHIPPED: {OrderStatus.DELIVERED},
    OrderStatus.DELIVERED: set(),
    OrderStatus.CANCELLED: set(),
}
RESERVABLE_STATUSES = {OrderStatus.PENDING_PAYMENT, OrderStatus.PAID}


def _created_at() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace(
        "+00:00", "Z"
    )


def _load_order(connection: sqlite3.Connection, order_id: str) -> Optional[Dict[str, Any]]:
    order = connection.execute(
        "SELECT * FROM orders WHERE id = ?", (order_id,)
    ).fetchone()
    if order is None:
        return None

    items = connection.execute(
        """
        SELECT product_id, name, price, quantity
        FROM order_items
        WHERE order_id = ?
        ORDER BY id
        """,
        (order_id,),
    ).fetchall()
    return {
        "id": order["id"],
        "userId": order["user_id"],
        "customer": {
            "name": order["customer_name"],
            "address": order["customer_address"],
            "city": order["customer_city"],
        },
        "items": [
            {
                "productId": item["product_id"],
                "name": item["name"],
                "price": item["price"],
                "quantity": item["quantity"],
            }
            for item in items
        ],
        "total": order["total"],
        "status": order["status"],
        "createdAt": order["created_at"],
    }


def get_order(database_path: DatabasePath, order_id: str) -> Dict[str, Any]:
    with get_connection(database_path) as connection:
        order = _load_order(connection, order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found.")
    return order


def get_orders(database_path: DatabasePath, user_id: str) -> List[Dict[str, Any]]:
    with get_connection(database_path) as connection:
        rows = connection.execute(
            "SELECT id FROM orders WHERE user_id = ? ORDER BY created_at DESC, id",
            (user_id,),
        ).fetchall()
        return [
            order
            for row in rows
            if (order := _load_order(connection, row["id"])) is not None
        ]


def _upstream_message(response: httpx.Response, fallback: str) -> str:
    try:
        body = response.json()
    except ValueError:
        return fallback
    if isinstance(body, dict) and isinstance(body.get("message"), str):
        return body["message"]
    return fallback


def _parse_product(product_id: int, response: httpx.Response) -> Tuple[str, float]:
    if response.status_code == 404:
        raise HTTPException(
            status_code=404,
            detail=f"Product {product_id} was not found in the catalog.",
        )
    if response.is_error:
        logger.warning(
            "Catalog returned HTTP %s while loading product %s",
            response.status_code,
            product_id,
        )
        raise HTTPException(
            status_code=502,
            detail="The catalog service could not provide product information.",
        )
    try:
        product = response.json()
        name = product["name"]
        raw_price = product["price"]
        price_decimal = Decimal(str(raw_price))
        price = float(price_decimal)
        if (
            not isinstance(name, str)
            or not name.strip()
            or isinstance(raw_price, bool)
            or not price_decimal.is_finite()
            or price < 0
            or not math.isfinite(price)
        ):
            raise ValueError("Invalid product fields")
    except (KeyError, TypeError, ValueError, InvalidOperation):
        logger.warning("Catalog returned invalid information for product %s", product_id)
        raise HTTPException(
            status_code=502,
            detail="The catalog service returned invalid product information.",
        )
    return name.strip(), price


async def _catalog_products(
    client: httpx.AsyncClient,
    catalog_url: str,
    product_ids: List[int],
) -> Dict[int, Tuple[str, float]]:
    try:
        responses = await asyncio.gather(
            *(
                client.get(f"{catalog_url.rstrip('/')}/products/{product_id}")
                for product_id in product_ids
            )
        )
    except httpx.TimeoutException:
        logger.warning("Catalog request timed out")
        raise HTTPException(
            status_code=504, detail="The catalog service timed out."
        )
    except httpx.RequestError:
        logger.exception("Could not reach catalog service")
        raise HTTPException(
            status_code=503, detail="The catalog service is unavailable."
        )
    return {
        product_id: _parse_product(product_id, response)
        for product_id, response in zip(product_ids, responses)
    }


async def _reserve_inventory(
    client: httpx.AsyncClient, inventory_url: str, items: List[Dict[str, int]]
) -> None:
    try:
        response = await client.post(
            f"{inventory_url.rstrip('/')}/api/inventory/reserve",
            json={"items": items},
        )
    except httpx.TimeoutException:
        logger.warning("Inventory reservation request timed out")
        raise HTTPException(
            status_code=504,
            detail="The inventory service timed out while reserving stock.",
        )
    except httpx.RequestError:
        logger.exception("Could not reach inventory service")
        raise HTTPException(
            status_code=503,
            detail="The inventory service is unavailable.",
        )
    if response.is_error:
        message = _upstream_message(response, "Inventory reservation failed.")
        status_code = 409 if response.status_code == 409 else 502
        raise HTTPException(status_code=status_code, detail=message)


async def _release_inventory(
    client: httpx.AsyncClient, inventory_url: str, items: List[Dict[str, int]]
) -> None:
    try:
        response = await client.post(
            f"{inventory_url.rstrip('/')}/api/inventory/release",
            json={"items": items},
        )
    except httpx.TimeoutException:
        logger.warning("Inventory release request timed out")
        raise HTTPException(
            status_code=504,
            detail="The inventory service timed out while releasing stock.",
        )
    except httpx.RequestError:
        logger.exception("Could not reach inventory service")
        raise HTTPException(
            status_code=503,
            detail="The inventory service is unavailable.",
        )
    if response.is_error:
        message = _upstream_message(response, "Inventory release failed.")
        status_code = 409 if response.status_code == 409 else 502
        raise HTTPException(status_code=status_code, detail=message)


async def create_order(
    database_path: DatabasePath,
    client: httpx.AsyncClient,
    catalog_url: str,
    inventory_url: str,
    payload: CreateOrderInput,
) -> Dict[str, Any]:
    quantities: Dict[int, int] = {}
    for item in payload.items:
        quantities[item.product_id] = (
            quantities.get(item.product_id, 0) + item.quantity
        )
        if quantities[item.product_id] > 10000:
            raise HTTPException(
                status_code=400,
                detail="Combined quantity for a product cannot exceed 10000.",
            )

    product_ids = list(quantities)
    products = await _catalog_products(client, catalog_url, product_ids)
    order_items = [
        {
            "productId": product_id,
            "name": products[product_id][0],
            "price": products[product_id][1],
            "quantity": quantities[product_id],
        }
        for product_id in product_ids
    ]
    inventory_items = [
        {"productId": item["productId"], "quantity": item["quantity"]}
        for item in order_items
    ]
    total_decimal = sum(
        (
            Decimal(str(item["price"])) * item["quantity"]
            for item in order_items
        ),
        Decimal("0"),
    ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    total = float(total_decimal)
    if not math.isfinite(total):
        raise HTTPException(status_code=400, detail="Order total is invalid.")

    await _reserve_inventory(client, inventory_url, inventory_items)
    order_id = str(uuid4())
    created_at = _created_at()
    try:
        with get_connection(database_path) as connection:
            connection.execute(
                """
                INSERT INTO orders (
                    id, user_id, customer_name, customer_address,
                    customer_city, total, status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    order_id,
                    payload.user_id,
                    payload.customer.name,
                    payload.customer.address,
                    payload.customer.city,
                    total,
                    OrderStatus.PENDING_PAYMENT.value,
                    created_at,
                ),
            )
            connection.executemany(
                """
                INSERT INTO order_items (order_id, product_id, name, price, quantity)
                VALUES (?, ?, ?, ?, ?)
                """,
                [
                    (
                        order_id,
                        item["productId"],
                        item["name"],
                        item["price"],
                        item["quantity"],
                    )
                    for item in order_items
                ],
            )
    except sqlite3.Error:
        logger.exception("Could not persist order %s", order_id)
        try:
            await _release_inventory(client, inventory_url, inventory_items)
        except HTTPException:
            logger.exception(
                "Could not compensate inventory reservation for order %s",
                order_id,
            )
            raise HTTPException(
                status_code=500,
                detail=(
                    "Order creation failed and reserved stock could not be "
                    "released. Contact support."
                ),
            )
        raise HTTPException(
            status_code=500,
            detail="Order could not be saved. Reserved stock was released.",
        )
    return get_order(database_path, order_id)


def _load_order_and_status(
    connection: sqlite3.Connection, order_id: str
) -> Tuple[Dict[str, Any], OrderStatus]:
    row = connection.execute(
        "SELECT status FROM orders WHERE id = ?", (order_id,)
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Order not found.")
    try:
        status = OrderStatus(row["status"])
    except ValueError:
        logger.error("Order %s has an unsupported status %r", order_id, row["status"])
        raise HTTPException(
            status_code=409, detail="Order has an unsupported current status."
        )
    order = _load_order(connection, order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found.")
    return order, status


async def update_order_status(
    database_path: DatabasePath,
    client: httpx.AsyncClient,
    inventory_url: str,
    order_id: str,
    new_status: OrderStatus,
) -> Dict[str, Any]:
    if new_status == OrderStatus.CANCELLED:
        return await cancel_order(database_path, client, inventory_url, order_id)

    with get_connection(database_path) as connection:
        connection.execute("BEGIN IMMEDIATE")
        _, current_status = _load_order_and_status(connection, order_id)
        # Same status again is accepted without change (idempotent): Shipping sets
        # SHIPPED/DELIVERED, then the frontend tracker sends the same status.
        if new_status != current_status:
            if new_status not in STATUS_TRANSITIONS[current_status]:
                raise HTTPException(
                    status_code=409,
                    detail=f"Invalid status transition: {current_status.value} to {new_status.value}.",
                )
            connection.execute(
                "UPDATE orders SET status = ? WHERE id = ?",
                (new_status.value, order_id),
            )
    return get_order(database_path, order_id)


async def cancel_order(
    database_path: DatabasePath,
    client: httpx.AsyncClient,
    inventory_url: str,
    order_id: str,
) -> Dict[str, Any]:
    with get_connection(database_path) as connection:
        connection.execute("BEGIN IMMEDIATE")
        order, current_status = _load_order_and_status(connection, order_id)
        if current_status not in RESERVABLE_STATUSES:
            raise HTTPException(
                status_code=409,
                detail="This order cannot be cancelled in its current status.",
            )
        previous_status = current_status.value
        connection.execute(
            "UPDATE orders SET status = ? WHERE id = ?",
            (OrderStatus.CANCELLED.value, order_id),
        )

    items = [
        {"productId": item["productId"], "quantity": item["quantity"]}
        for item in order["items"]
    ]
    try:
        await _release_inventory(client, inventory_url, items)
    except HTTPException:
        try:
            with get_connection(database_path) as connection:
                connection.execute(
                    "UPDATE orders SET status = ? WHERE id = ? AND status = ?",
                    (previous_status, order_id, OrderStatus.CANCELLED.value),
                )
        except sqlite3.Error:
            logger.exception("Could not restore status for cancelled order %s", order_id)
            raise HTTPException(
                status_code=500,
                detail=(
                    "Inventory release failed and the order status could not be "
                    "restored. Contact support."
                ),
            )
        raise
    return get_order(database_path, order_id)
