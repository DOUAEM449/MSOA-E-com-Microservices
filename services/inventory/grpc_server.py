"""gRPC server of the Inventory service (LAB 4 - high-performance communication).

Implements `inventory.InventoryService` from proto/inventory.proto. It runs in the
same process as the REST API (started from main.py) and uses the same database,
so stock is consistent whichever interface a client uses. REST stays available
for the frontend; Orders uses gRPC.
"""
import logging
import os
import sqlite3
from concurrent import futures
from typing import Dict, Optional

import grpc

import database
import inventory_pb2
import inventory_pb2_grpc

logger = logging.getLogger("uvicorn.error")  # shown in the uvicorn console

DEFAULT_GRPC_PORT = 50051


class _RpcError(Exception):
    def __init__(self, code: grpc.StatusCode, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def _parse_product_id(raw: str) -> int:
    try:
        product_id = int(str(raw).strip())
    except ValueError:
        raise _RpcError(grpc.StatusCode.INVALID_ARGUMENT, f"Invalid productId: {raw!r}")
    if product_id <= 0:
        raise _RpcError(grpc.StatusCode.INVALID_ARGUMENT, f"Invalid productId: {raw!r}")
    return product_id


def _parse_quantity(quantity: int) -> int:
    if quantity <= 0:
        raise _RpcError(grpc.StatusCode.INVALID_ARGUMENT, "quantity must be greater than 0")
    return quantity


def _aggregate(items) -> Dict[int, int]:
    if not items:
        raise _RpcError(grpc.StatusCode.INVALID_ARGUMENT, "items must not be empty")
    quantities: Dict[int, int] = {}
    for item in items:
        product_id = _parse_product_id(item.productId)
        quantities[product_id] = quantities.get(product_id, 0) + _parse_quantity(item.quantity)
    return quantities


def _stock_of(conn: sqlite3.Connection, product_id: int) -> Optional[int]:
    row = conn.execute(
        "SELECT quantity FROM stock WHERE product_id = ?", (product_id,)
    ).fetchone()
    return None if row is None else row["quantity"]


def check_availability(product_id_raw: str, quantity: int) -> inventory_pb2.AvailabilityResponse:
    product_id = _parse_product_id(product_id_raw)
    quantity = _parse_quantity(quantity)
    conn = database.get_connection()
    try:
        stock = _stock_of(conn, product_id)
    finally:
        conn.close()
    if stock is None:
        raise _RpcError(grpc.StatusCode.NOT_FOUND, f"Product {product_id} not found")
    return inventory_pb2.AvailabilityResponse(available=stock >= quantity, availableQuantity=stock)


def reserve_stock(items) -> inventory_pb2.StockResponse:
    quantities = _aggregate(items)
    conn = database.get_connection()
    try:
        conn.execute("BEGIN IMMEDIATE")
        for product_id, requested in quantities.items():
            stock = _stock_of(conn, product_id)
            if stock is None or stock < requested:
                conn.execute("ROLLBACK")
                raise _RpcError(
                    grpc.StatusCode.FAILED_PRECONDITION,
                    f"Insufficient stock for product {product_id}",
                )
        for product_id, requested in quantities.items():
            conn.execute(
                "UPDATE stock SET quantity = quantity - ?, updated_at = CURRENT_TIMESTAMP "
                "WHERE product_id = ?",
                (requested, product_id),
            )
        conn.execute("COMMIT")
        return inventory_pb2.StockResponse(success=True)
    except sqlite3.Error:
        if conn.in_transaction:
            conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()


def release_stock(items) -> inventory_pb2.StockResponse:
    quantities = _aggregate(items)
    conn = database.get_connection()
    try:
        conn.execute("BEGIN IMMEDIATE")
        for product_id in quantities:
            if _stock_of(conn, product_id) is None:
                conn.execute("ROLLBACK")
                raise _RpcError(grpc.StatusCode.NOT_FOUND, f"Product {product_id} not found")
        for product_id, quantity in quantities.items():
            conn.execute(
                "UPDATE stock SET quantity = quantity + ?, updated_at = CURRENT_TIMESTAMP "
                "WHERE product_id = ?",
                (quantity, product_id),
            )
        conn.execute("COMMIT")
        return inventory_pb2.StockResponse(success=True)
    except sqlite3.Error:
        if conn.in_transaction:
            conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()


class InventoryServicer(inventory_pb2_grpc.InventoryServiceServicer):
    """Translates gRPC calls to the stock logic and errors to gRPC status codes."""

    def _run(self, context, operation, *args):
        name = operation.__name__
        try:
            response = operation(*args)
            logger.info("gRPC %s OK -> %s", name, str(response).replace("\n", " ").strip())
            return response
        except _RpcError as error:
            logger.info("gRPC %s -> %s: %s", name, error.code.name, error.message)
            context.abort(error.code, error.message)
        except sqlite3.Error:
            logger.exception("Inventory database error")
            context.abort(grpc.StatusCode.INTERNAL, "Internal inventory error")

    def CheckAvailability(self, request, context):
        return self._run(context, check_availability, request.productId, request.quantity)

    def ReserveStock(self, request, context):
        return self._run(context, reserve_stock, request.items)

    def ReleaseStock(self, request, context):
        return self._run(context, release_stock, request.items)


def grpc_port() -> int:
    return int(os.getenv("INVENTORY_GRPC_PORT", str(DEFAULT_GRPC_PORT)))


def create_server(port: Optional[int] = None) -> grpc.Server:
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    inventory_pb2_grpc.add_InventoryServiceServicer_to_server(InventoryServicer(), server)
    bound = server.add_insecure_port(f"[::]:{grpc_port() if port is None else port}")
    if bound == 0:
        raise RuntimeError(f"Could not bind the gRPC server to port {port or grpc_port()}")
    server.bound_port = bound
    return server


if __name__ == "__main__":
    # Standalone mode: gRPC only (REST is started with uvicorn main:app).
    logging.basicConfig(level=logging.INFO)
    database.initialize_database()
    srv = create_server()
    srv.start()
    logger.info("Inventory gRPC server listening on port %s", srv.bound_port)
    srv.wait_for_termination()
