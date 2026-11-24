import sys
from pathlib import Path
from typing import Optional

from fastapi.testclient import TestClient
import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from main import create_app


# ── Helpers ──────────────────────────────────────────────────────

ORDER_PENDING = {
    "id": "order-001",
    "userId": "user-1",
    "customer": {"name": "Demo", "address": "123 Main", "city": "Casablanca"},
    "items": [{"productId": 1, "name": "Lenovo ThinkPad E14", "price": 8499, "quantity": 2}],
    "total": 16998,
    "status": "PENDING_PAYMENT",
    "createdAt": "2026-11-18T12:00:00.000Z",
}

ORDER_PAID = {**ORDER_PENDING, "status": "PAID"}


def make_client(
    tmp_path: Path,
    order: Optional[dict] = None,
    patch_status: int = 200,
    orders_down: bool = False,
) -> TestClient:
    """Create a TestClient with a mock Orders service."""

    if order is None:
        order = ORDER_PENDING

    def upstream(request: httpx.Request) -> httpx.Response:
        path = request.url.path

        if orders_down:
            raise httpx.ConnectError("Orders service is down")

        # GET /api/orders/{orderId}
        if request.method == "GET" and path.startswith("/api/orders/"):
            order_id = path.split("/")[-1]
            if order_id == order["id"]:
                return httpx.Response(200, json=order)
            return httpx.Response(404, json={"message": "Order not found."})

        # PATCH /api/orders/{orderId}/status
        if request.method == "PATCH" and "/status" in path:
            if patch_status == 200:
                patched = {**order, "status": "PAID"}
                return httpx.Response(200, json=patched)
            if patch_status == 409:
                return httpx.Response(409, json={"message": "Invalid transition"})
            return httpx.Response(500, json={"message": "Internal error"})

        return httpx.Response(404, json={"message": "Unexpected request"})

    app = create_app(
        database_path=tmp_path / "payments.db",
        orders_url="http://orders.test",
        http_transport=httpx.MockTransport(upstream),
    )
    return TestClient(app)


# ── Tests ────────────────────────────────────────────────────────


def test_health(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "UP"


def test_list_payments_empty(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        resp = client.get("/api/payments")
    assert resp.status_code == 200
    assert resp.json() == []


def test_create_payment_success(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        resp = client.post(
            "/api/payments",
            json={"orderId": "order-001", "method": "CARD"},
        )
    assert resp.status_code == 201
    payment = resp.json()
    assert payment["orderId"] == "order-001"
    assert payment["amount"] == 16998
    assert payment["method"] == "CARD"
    assert payment["status"] == "SUCCESS"
    assert "id" in payment
    assert "createdAt" in payment


def test_create_and_list_payments(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        created = client.post(
            "/api/payments",
            json={"orderId": "order-001", "method": "CARD"},
        )
        assert created.status_code == 201

        listed = client.get("/api/payments")
        assert listed.status_code == 200
        payments = listed.json()
        assert len(payments) == 1
        assert payments[0]["orderId"] == "order-001"


def test_get_payment_by_order(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        client.post(
            "/api/payments",
            json={"orderId": "order-001", "method": "CARD"},
        )
        resp = client.get("/api/payments/order/order-001")
    assert resp.status_code == 200
    assert resp.json()["orderId"] == "order-001"


def test_get_payment_by_order_not_found(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        resp = client.get("/api/payments/order/order-999")
    assert resp.status_code == 404
    assert resp.json() == {"message": "No payment found for order order-999"}


def test_duplicate_payment_returns_409(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        first = client.post(
            "/api/payments",
            json={"orderId": "order-001", "method": "CARD"},
        )
        assert first.status_code == 201

        second = client.post(
            "/api/payments",
            json={"orderId": "order-001", "method": "CARD"},
        )
    assert second.status_code == 409
    assert "already exists" in second.json()["message"]


def test_order_not_found_returns_404(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        resp = client.post(
            "/api/payments",
            json={"orderId": "order-999", "method": "CARD"},
        )
    assert resp.status_code == 404
    assert "not found" in resp.json()["message"]


def test_order_not_pending_payment_returns_409(tmp_path: Path) -> None:
    with make_client(tmp_path, order=ORDER_PAID) as client:
        resp = client.post(
            "/api/payments",
            json={"orderId": "order-001", "method": "CARD"},
        )
    assert resp.status_code == 409
    assert "not pending payment" in resp.json()["message"]


def test_missing_orderId_returns_400(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        resp = client.post(
            "/api/payments",
            json={"method": "CARD"},
        )
    assert resp.status_code == 400
    assert "message" in resp.json()


def test_missing_method_returns_400(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        resp = client.post(
            "/api/payments",
            json={"orderId": "order-001"},
        )
    assert resp.status_code == 400
    assert "message" in resp.json()


def test_orders_service_unavailable_returns_503(tmp_path: Path) -> None:
    with make_client(tmp_path, orders_down=True) as client:
        resp = client.post(
            "/api/payments",
            json={"orderId": "order-001", "method": "CARD"},
        )
    assert resp.status_code == 503
    assert "unavailable" in resp.json()["message"]


def test_patch_failure_rolls_back_payment(tmp_path: Path) -> None:
    """When PATCH to PAID fails, the payment must be deleted (compensation)."""
    with make_client(tmp_path, patch_status=500) as client:
        resp = client.post(
            "/api/payments",
            json={"orderId": "order-001", "method": "CARD"},
        )
        # The payment creation should fail
        assert resp.status_code in (502, 503)

        # Verify no payment was persisted
        listed = client.get("/api/payments")
        assert listed.json() == []


def test_patch_409_rolls_back_payment(tmp_path: Path) -> None:
    """When PATCH returns 409 (order cancelled), the payment must be deleted."""
    with make_client(tmp_path, patch_status=409) as client:
        resp = client.post(
            "/api/payments",
            json={"orderId": "order-001", "method": "CARD"},
        )
        assert resp.status_code == 409

        listed = client.get("/api/payments")
        assert listed.json() == []


def test_validation_errors_use_message_shape(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        resp = client.post("/api/payments", json={})
    assert resp.status_code == 400
    assert set(resp.json()) == {"message"}


def test_cors_preflight(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        resp = client.options(
            "/api/payments",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            },
        )
    assert resp.status_code == 200
    assert resp.headers["access-control-allow-origin"] == "http://localhost:5173"
