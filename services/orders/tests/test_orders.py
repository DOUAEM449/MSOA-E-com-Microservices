import sys
from pathlib import Path
from typing import Dict

from fastapi.testclient import TestClient
import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from main import create_app


def make_client(
    tmp_path: Path,
    stock_available: bool = True,
    release_succeeds: bool = True,
) -> TestClient:
    def upstream(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/products/12":
            return httpx.Response(
                200, json={"id": 12, "name": "Catalog Mouse", "price": 12.5}
            )
        if request.url.path == "/products/13":
            return httpx.Response(status_code=404, json={"message": "Not found"})
        if request.url.path == "/api/inventory/reserve":
            if not stock_available:
                return httpx.Response(
                    status_code=409, json={"message": "Insufficient stock."}
                )
            return httpx.Response(200, json={"success": True})
        if request.url.path == "/api/inventory/release":
            if not release_succeeds:
                return httpx.Response(
                    status_code=503, json={"message": "Inventory is unavailable."}
                )
            return httpx.Response(200, json={"success": True})
        return httpx.Response(status_code=404, json={"message": "Unexpected request"})

    app = create_app(
        database_path=tmp_path / "orders.db",
        catalog_url="http://catalog.test",
        inventory_url="http://inventory.test",
        http_transport=httpx.MockTransport(upstream),
    )
    return TestClient(app)


def create_payload() -> Dict:
    return {
        "userId": "user-1",
        "customer": {
            "name": "Customer",
            "email": "customer@example.test",
            "address": "123 Main Street",
            "city": "Casablanca",
        },
        "items": [{"productId": 12, "quantity": 2}],
    }


def test_create_list_update_and_cancel_order(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        created = client.post("/api/orders", json=create_payload())
        assert created.status_code == 201
        order = created.json()
        assert order["total"] == 25.0
        assert order["items"] == [
            {
                "productId": 12,
                "name": "Catalog Mouse",
                "price": 12.5,
                "quantity": 2,
            }
        ]
        assert order["status"] == "PENDING_PAYMENT"

        assert client.get("/api/orders?userId=user-1").json() == [order]
        assert client.get(f"/api/orders/{order['id']}").json() == order
        assert (
            client.patch(
                f"/api/orders/{order['id']}/status", json={"status": "PAID"}
            ).json()["status"]
            == "PAID"
        )
        cancelled = client.post(f"/api/orders/{order['id']}/cancel")
        assert cancelled.status_code == 200
        assert cancelled.json()["status"] == "CANCELLED"


def test_validation_errors_use_message_shape(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        response = client.post("/api/orders", json={"userId": "user-1"})
    assert response.status_code == 400
    assert set(response.json()) == {"message"}
    assert response.json()["message"].startswith("Validation error")


def test_missing_product_and_stock_shortage_do_not_persist_order(
    tmp_path: Path,
) -> None:
    with make_client(tmp_path, stock_available=False) as client:
        unavailable = client.post("/api/orders", json=create_payload())
        missing_payload = create_payload()
        missing_payload["items"][0]["productId"] = 13
        missing_product = client.post("/api/orders", json=missing_payload)

        assert unavailable.status_code == 409
        assert unavailable.json() == {"message": "Insufficient stock."}
        assert missing_product.status_code == 404
        assert client.get("/api/orders?userId=user-1").json() == []


def test_missing_order_and_invalid_transition_are_json_errors(
    tmp_path: Path,
) -> None:
    with make_client(tmp_path) as client:
        missing = client.get("/api/orders/missing")
        created = client.post("/api/orders", json=create_payload()).json()
        invalid = client.patch(
            f"/api/orders/{created['id']}/status", json={"status": "DELIVERED"}
        )

    assert missing.status_code == 404
    assert missing.json() == {"message": "Order not found."}
    assert invalid.status_code == 409
    assert set(invalid.json()) == {"message"}


def test_failed_inventory_release_restores_order_status(tmp_path: Path) -> None:
    with make_client(tmp_path, release_succeeds=False) as client:
        created = client.post("/api/orders", json=create_payload()).json()
        cancelled = client.post(f"/api/orders/{created['id']}/cancel")
        current = client.get(f"/api/orders/{created['id']}")

    assert cancelled.status_code == 502
    assert cancelled.json() == {"message": "Inventory is unavailable."}
    assert current.json()["status"] == "PENDING_PAYMENT"


def test_cors_preflight_allows_only_configured_methods_and_headers(
    tmp_path: Path,
) -> None:
    with make_client(tmp_path) as client:
        response = client.options(
            "/api/orders",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "PATCH",
                "Access-Control-Request-Headers": "authorization,content-type",
            },
        )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
    allowed_headers = {
        header.strip().lower()
        for header in response.headers["access-control-allow-headers"].split(",")
    }
    assert {"authorization", "content-type"}.issubset(allowed_headers)
    assert set(response.headers["access-control-allow-methods"].split(", ")) == {
        "GET",
        "POST",
        "PATCH",
        "OPTIONS",
    }
