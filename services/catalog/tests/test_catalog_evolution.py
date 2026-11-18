import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from main import app


client = TestClient(app)


def test_legacy_contract_keeps_numeric_price():
    response = client.get("/api/v1/products/1")

    assert response.status_code == 200
    product = response.json()
    assert isinstance(product["price"], (int, float))
    assert product["price"] == 8499


def test_v2_contract_returns_currency_aware_price():
    response = client.get("/api/v2/products/1")

    assert response.status_code == 200
    price = response.json()["price"]
    assert price["amount"] == 8499
    assert price["currency"] == "MAD"


def test_legacy_unversioned_endpoint_remains_compatible():
    response = client.get("/products/1")

    assert response.status_code == 200
    assert isinstance(response.json()["price"], (int, float))


def test_missing_product_returns_not_found():
    assert client.get("/api/v2/products/999999").status_code == 404
