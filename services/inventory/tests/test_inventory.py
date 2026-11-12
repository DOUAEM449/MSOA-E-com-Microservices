
import pytest
import database
import shutil
from pathlib import Path
from fastapi.testclient import TestClient
from main import app


@pytest.fixture
def client(tmp_path, monkeypatch):

    test_db = tmp_path / "inventory.db"

    source_db_dir = (
        Path(database.__file__).resolve().parent / "db"
    )

    shutil.copy(source_db_dir / "schema.sql", tmp_path)
    shutil.copy(source_db_dir / "seed.sql", tmp_path)

    monkeypatch.setattr(database, "DB_PATH", test_db)
    monkeypatch.setattr(database, "DB_DIR", tmp_path)

    with TestClient(app) as test_client:
        yield test_client


def test_home(client):
    response = client.get("/")

    assert response.status_code == 200
    assert response.json()["service"] == "Inventory"


def test_get_stock(client):
    response = client.get("/api/inventory/1")

    assert response.status_code == 200
    assert response.json()["stock"] == 12


def test_product_not_found(client):
    response = client.get("/api/inventory/99")

    assert response.status_code == 404


def test_check_available_stock(client):
    response = client.post(
        "/api/inventory/check",
        json={
            "items": [
                {"productId": 1, "quantity": 2}
            ]
        }
    )

    assert response.status_code == 200
    assert response.json()["available"] is True


def test_check_insufficient_stock(client):
    response = client.post(
        "/api/inventory/check",
        json={
            "items": [
                {"productId": 1, "quantity": 100}
            ]
        }
    )

    assert response.json()["available"] is False


def test_reserve_stock(client):
    response = client.post(
        "/api/inventory/reserve",
        json={
            "items": [
                {"productId": 1, "quantity": 2}
            ]
        }
    )

    assert response.status_code == 200
    assert response.json()["success"] is True

    stock = client.get("/api/inventory/1")

    assert stock.json()["stock"] == 10


def test_reservation_atomicity(client):

    response = client.post(
        "/api/inventory/reserve",
        json={
            "items": [
                {"productId": 1, "quantity": 2},
                {"productId": 2, "quantity": 100}
            ]
        }
    )

    assert response.status_code == 409

    # Product 1 must remain unchanged
    stock1 = client.get("/api/inventory/1")
    assert stock1.json()["stock"] == 12

    # Product 2 must also remain unchanged
    stock2 = client.get("/api/inventory/2")
    assert stock2.json()["stock"] == 20


def test_release_stock(client):

    client.post(
        "/api/inventory/reserve",
        json={
            "items": [
                {"productId": 1, "quantity": 2}
            ]
        }
    )

    response = client.post(
        "/api/inventory/release",
        json={
            "items": [
                {"productId": 1, "quantity": 2}
            ]
        }
    )

    assert response.status_code == 200
    assert response.json()["success"] is True

    stock = client.get("/api/inventory/1")

    assert stock.json()["stock"] == 12
