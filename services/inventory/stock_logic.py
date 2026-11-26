"""Stock business rules of the Inventory service.

Single source of truth used by BOTH interfaces (LAB4_CONTRACTS.md, section 1):
  * the REST API  (main.py)        -> errors mapped to HTTP status codes
  * the gRPC API  (grpc_server.py) -> errors mapped to gRPC status codes
Functions take already-validated quantities {productId: quantity}.
"""
import sqlite3
from typing import Dict, Iterable, Optional, Tuple

import database


class StockError(Exception):
    """Base class: `message` is safe to show to the client."""

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class ProductNotFound(StockError):
    pass


class InsufficientStock(StockError):
    pass


def aggregate(pairs: Iterable[Tuple[int, int]]) -> Dict[int, int]:
    """Sum quantities of duplicate product lines."""
    quantities: Dict[int, int] = {}
    for product_id, quantity in pairs:
        quantities[product_id] = quantities.get(product_id, 0) + quantity
    return quantities


def _stock_of(conn: sqlite3.Connection, product_id: int) -> Optional[int]:
    row = conn.execute(
        "SELECT quantity FROM stock WHERE product_id = ?", (product_id,)
    ).fetchone()
    return None if row is None else row["quantity"]


def get_stock(product_id: int) -> int:
    """Current stock of one product. Raises ProductNotFound."""
    conn = database.get_connection()
    try:
        stock = _stock_of(conn, product_id)
    finally:
        conn.close()
    if stock is None:
        raise ProductNotFound(f"Product {product_id} not found")
    return stock


def is_available(quantities: Dict[int, int]) -> bool:
    """True if every line can be served (unknown product -> False)."""
    conn = database.get_connection()
    try:
        for product_id, requested in quantities.items():
            stock = _stock_of(conn, product_id)
            if stock is None or stock < requested:
                return False
        return True
    finally:
        conn.close()


def _apply(quantities: Dict[int, int], sign: int, check) -> None:
    conn = database.get_connection()
    try:
        conn.execute("BEGIN IMMEDIATE")
        for product_id, quantity in quantities.items():
            check(product_id, quantity, _stock_of(conn, product_id))
        for product_id, quantity in quantities.items():
            conn.execute(
                "UPDATE stock SET quantity = quantity + ?, updated_at = CURRENT_TIMESTAMP "
                "WHERE product_id = ?",
                (sign * quantity, product_id),
            )
        conn.execute("COMMIT")
    except BaseException:
        if conn.in_transaction:
            conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()


def reserve(quantities: Dict[int, int]) -> None:
    """Atomically take every line, or nothing. Raises InsufficientStock."""
    def check(product_id, requested, stock):
        if stock is None or stock < requested:
            raise InsufficientStock(f"Insufficient stock for product {product_id}")
    _apply(quantities, -1, check)


def release(quantities: Dict[int, int]) -> None:
    """Atomically give every line back. Raises ProductNotFound."""
    def check(product_id, _quantity, stock):
        if stock is None:
            raise ProductNotFound(f"Product {product_id} not found")
    _apply(quantities, +1, check)
