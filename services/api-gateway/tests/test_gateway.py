"""Lab 5 — Gateway skeleton: health, routing table, static forwarding, 404 / 503."""

import json
import sys
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import config
import routes
from main import create_app

SERVICES = {
    "auth-service": "http://auth.test",
    "catalog-service": "http://catalog.test",
    "orders-service": "http://orders.test",
}


class Backend:
    """Fake backend: records every request it receives and answers with a fixed response."""

    def __init__(self, status: int = 200, body=None, headers=None):
        self.requests = []
        self.status = status
        self.body = body if body is not None else {"ok": True}
        self.headers = headers or {}

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return httpx.Response(self.status, json=self.body, headers=self.headers)


def make_client(backend: Backend, services=None) -> TestClient:
    app = create_app(
        services=services if services is not None else SERVICES,
        transport=httpx.MockTransport(backend),
    )
    return TestClient(app)


# ── Routing table ───────────────────────────────────────────────


@pytest.mark.parametrize(
    "path, expected",
    [
        ("/api/auth/login", "auth-service"),
        ("/products", "catalog-service"),
        ("/products/3", "catalog-service"),
        ("/api/v1/products", "catalog-service"),
        ("/api/v2/products/7", "catalog-service"),
        ("/api/inventory/check", "inventory-service"),
        ("/api/orders", "orders-service"),
        ("/api/orders/order-1/status", "orders-service"),
        ("/api/payments/order/order-1", "payments-service"),
        ("/api/shipments", "shipping-service"),
        ("/activity", "analytics-service"),
        ("/api/analytics/summary", "events-analytics-service"),
    ],
)
def test_match_known_paths(path, expected):
    assert routes.match(path) == expected


@pytest.mark.parametrize("path", ["/", "/xyz", "/productsX", "/api", "/api/ordersfoo"])
def test_match_unknown_paths(path):
    assert routes.match(path) is None


def test_static_services_env_override(monkeypatch):
    monkeypatch.setenv("CATALOG_SERVICE_URL", "http://127.0.0.1:9192/")
    monkeypatch.delenv("ANALYTICS_SERVICE_URL", raising=False)
    services = config.static_services()
    assert services["catalog-service"] == "http://127.0.0.1:9192"
    assert services["orders-service"] == "http://127.0.0.1:8084"
    assert "analytics-service" not in services


def test_analytics_service_added_when_configured(monkeypatch):
    monkeypatch.setenv("ANALYTICS_SERVICE_URL", "http://127.0.0.1:9000")
    assert config.static_services()["analytics-service"] == "http://127.0.0.1:9000"


# ── Gateway endpoints ───────────────────────────────────────────


def test_health_is_answered_by_the_gateway():
    backend = Backend()
    with make_client(backend) as client:
        resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "UP", "service": "api-gateway"}
    assert backend.requests == []


def test_unknown_path_returns_404():
    backend = Backend()
    with make_client(backend) as client:
        resp = client.get("/xyz")
    assert resp.status_code == 404
    assert resp.json() == {"error": "No route for /xyz"}
    assert backend.requests == []


def test_route_without_address_returns_503():
    backend = Backend()
    with make_client(backend) as client:
        resp = client.get("/api/payments")
    assert resp.status_code == 503
    assert resp.json() == {"error": "payments-service is not registered"}


# ── Static forwarding (Problem 1, 5b) ───────────────────────────


def test_get_is_forwarded_with_same_path_and_query():
    backend = Backend(body=[{"id": 1}])
    with make_client(backend) as client:
        resp = client.get("/products?category=Laptops&page=2")

    assert resp.status_code == 200
    assert resp.json() == [{"id": 1}]
    sent = backend.requests[0]
    assert sent.method == "GET"
    assert str(sent.url) == "http://catalog.test/products?category=Laptops&page=2"


def test_post_body_and_headers_are_forwarded():
    backend = Backend(status=201, body={"id": "order-1"})
    payload = {"userId": "u1", "items": [{"productId": 1, "quantity": 2}]}
    with make_client(backend) as client:
        resp = client.post(
            "/api/orders",
            json=payload,
            headers={"Authorization": "Bearer abc"},
        )

    assert resp.status_code == 201
    sent = backend.requests[0]
    assert sent.method == "POST"
    assert sent.url.path == "/api/orders"
    assert json.loads(sent.content) == payload
    assert sent.headers["authorization"] == "Bearer abc"
    assert sent.headers["host"] == "orders.test"


def test_service_errors_are_returned_unchanged():
    backend = Backend(status=409, body={"message": "Invalid transition"})
    with make_client(backend) as client:
        resp = client.patch("/api/orders/order-1/status", json={"status": "PAID"})
    assert resp.status_code == 409
    assert resp.json() == {"message": "Invalid transition"}


def test_response_headers_are_returned():
    backend = Backend(headers={"access-control-allow-origin": "http://localhost:5173"})
    with make_client(backend) as client:
        resp = client.get("/api/auth/me")
    assert resp.headers["access-control-allow-origin"] == "http://localhost:5173"
