"""Orders as gRPC client of Inventory (LAB 4, handout steps 5-6).

A small in-memory InventoryService (built from the same contract) plays the
server, so these tests only exercise the Orders side of the communication.
"""
import socket
import sys
from concurrent import futures
from pathlib import Path

import grpc
import httpx
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import inventory_pb2  # noqa: E402
import inventory_pb2_grpc  # noqa: E402
from main import create_app  # noqa: E402


class FakeInventory(inventory_pb2_grpc.InventoryServiceServicer):
    def __init__(self):
        self.stock = {"3": 8}
        self.calls = []

    def CheckAvailability(self, request, context):
        self.calls.append("CheckAvailability")
        if request.productId not in self.stock:
            context.abort(grpc.StatusCode.NOT_FOUND, f"Product {request.productId} not found")
        qty = self.stock[request.productId]
        return inventory_pb2.AvailabilityResponse(available=qty >= request.quantity, availableQuantity=qty)

    def ReserveStock(self, request, context):
        self.calls.append("ReserveStock")
        for item in request.items:
            if self.stock.get(item.productId, 0) < item.quantity:
                context.abort(grpc.StatusCode.FAILED_PRECONDITION, f"Insufficient stock for product {item.productId}")
        for item in request.items:
            self.stock[item.productId] -= item.quantity
        return inventory_pb2.StockResponse(success=True)

    def ReleaseStock(self, request, context):
        self.calls.append("ReleaseStock")
        for item in request.items:
            self.stock[item.productId] += item.quantity
        return inventory_pb2.StockResponse(success=True)


@pytest.fixture
def inventory():
    fake = FakeInventory()
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=4))
    inventory_pb2_grpc.add_InventoryServiceServicer_to_server(fake, server)
    fake.port = server.add_insecure_port("127.0.0.1:0")
    server.start()
    yield fake
    server.stop(grace=None)


def _catalog(request: httpx.Request) -> httpx.Response:
    if request.url.path == "/products/3":
        return httpx.Response(200, json={"id": 3, "name": "Keyboard", "price": 100.0})
    return httpx.Response(404, json={"message": "Not found"})


def _client(tmp_path, grpc_address):
    app = create_app(
        database_path=tmp_path / "orders.db",
        catalog_url="http://catalog.test",
        http_transport=httpx.MockTransport(_catalog),
        inventory_transport="grpc",
        inventory_grpc_address=grpc_address,
    )
    return TestClient(app)


def _order(quantity):
    return {
        "userId": "user-1",
        "customer": {"name": "C", "address": "1 Main St", "city": "Casablanca"},
        "items": [{"productId": 3, "quantity": quantity}],
    }


def _free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_order_checks_and_reserves_over_grpc(tmp_path, inventory):
    with _client(tmp_path, f"127.0.0.1:{inventory.port}") as client:
        r = client.post("/api/orders", json=_order(3))
        assert r.status_code == 201, r.text
        assert r.json()["total"] == 300.0
        assert inventory.calls == ["CheckAvailability", "ReserveStock"]
        assert inventory.stock["3"] == 5

        cancel = client.post(f"/api/orders/{r.json()['id']}/cancel")
        assert cancel.status_code == 200
        assert inventory.calls[-1] == "ReleaseStock"
        assert inventory.stock["3"] == 8


def test_insufficient_stock_is_rejected_before_reserving(tmp_path, inventory):
    with _client(tmp_path, f"127.0.0.1:{inventory.port}") as client:
        r = client.post("/api/orders", json=_order(10))
        assert r.status_code == 409
        assert r.json() == {"message": "Insufficient stock for product 3: requested 10, available 8."}
        assert "ReserveStock" not in inventory.calls
        assert client.get("/api/orders", params={"userId": "user-1"}).json() == []


def test_inventory_down_fails_cleanly_and_no_order(tmp_path):
    # Depending on the OS the client sees UNAVAILABLE (503) or DEADLINE_EXCEEDED (504).
    with _client(tmp_path, f"127.0.0.1:{_free_port()}") as client:
        r = client.post("/api/orders", json=_order(1))
        assert (r.status_code, r.json()) in [
            (503, {"message": "The inventory service is unavailable."}),
            (504, {"message": "The inventory service timed out."}),
        ]
        assert client.get("/api/orders", params={"userId": "user-1"}).json() == []
