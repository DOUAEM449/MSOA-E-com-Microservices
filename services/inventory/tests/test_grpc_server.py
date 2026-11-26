"""gRPC server tests (LAB 4): the scenarios of the gRPC handout, step 4."""
import shutil
import sys
from pathlib import Path

import grpc
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import database  # noqa: E402
import grpc_server  # noqa: E402
import inventory_pb2  # noqa: E402
import inventory_pb2_grpc  # noqa: E402


@pytest.fixture
def stub(tmp_path, monkeypatch):
    source = Path(database.__file__).resolve().parent / "db"
    shutil.copy(source / "schema.sql", tmp_path)
    shutil.copy(source / "seed.sql", tmp_path)
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "inventory.db")
    monkeypatch.setattr(database, "DB_DIR", tmp_path)
    database.initialize_database()

    server = grpc_server.create_server(port=0)  # any free port
    server.start()
    channel = grpc.insecure_channel(f"localhost:{server.bound_port}")
    try:
        yield inventory_pb2_grpc.InventoryServiceStub(channel)
    finally:
        channel.close()
        server.stop(grace=None)


def _check(stub, product_id, quantity):
    return stub.CheckAvailability(
        inventory_pb2.AvailabilityRequest(productId=product_id, quantity=quantity), timeout=2
    )


def _items(*pairs):
    return inventory_pb2.StockRequest(
        items=[inventory_pb2.StockItem(productId=p, quantity=q) for p, q in pairs]
    )


def test_sufficient_stock(stub):
    response = _check(stub, "3", 3)
    assert response.available is True
    assert response.availableQuantity == 8


def test_insufficient_stock(stub):
    response = _check(stub, "3", 10)
    assert response.available is False
    assert response.availableQuantity == 8


@pytest.mark.parametrize("product_id, quantity, code", [
    ("999", 2, grpc.StatusCode.NOT_FOUND),
    ("3", 0, grpc.StatusCode.INVALID_ARGUMENT),
    ("abc", 1, grpc.StatusCode.INVALID_ARGUMENT),
])
def test_check_errors(stub, product_id, quantity, code):
    with pytest.raises(grpc.RpcError) as error:
        _check(stub, product_id, quantity)
    assert error.value.code() == code


def test_reserve_and_release(stub):
    assert stub.ReserveStock(_items(("3", 3), ("1", 2)), timeout=2).success
    assert _check(stub, "3", 1).availableQuantity == 5
    assert _check(stub, "1", 1).availableQuantity == 10

    assert stub.ReleaseStock(_items(("3", 3), ("1", 2)), timeout=2).success
    assert _check(stub, "3", 1).availableQuantity == 8
    assert _check(stub, "1", 1).availableQuantity == 12


def test_reserve_is_atomic(stub):
    # product 1 is available, product 3 is not: nothing must change
    with pytest.raises(grpc.RpcError) as error:
        stub.ReserveStock(_items(("1", 2), ("3", 9)), timeout=2)
    assert error.value.code() == grpc.StatusCode.FAILED_PRECONDITION
    assert _check(stub, "1", 1).availableQuantity == 12
    assert _check(stub, "3", 1).availableQuantity == 8


def test_duplicate_lines_are_summed(stub):
    with pytest.raises(grpc.RpcError) as error:
        stub.ReserveStock(_items(("3", 5), ("3", 5)), timeout=2)
    assert error.value.code() == grpc.StatusCode.FAILED_PRECONDITION


def test_release_unknown_product(stub):
    with pytest.raises(grpc.RpcError) as error:
        stub.ReleaseStock(_items(("999", 1)), timeout=2)
    assert error.value.code() == grpc.StatusCode.NOT_FOUND


def test_empty_items_rejected(stub):
    with pytest.raises(grpc.RpcError) as error:
        stub.ReserveStock(inventory_pb2.StockRequest(), timeout=2)
    assert error.value.code() == grpc.StatusCode.INVALID_ARGUMENT


def test_rest_and_grpc_share_the_same_stock(stub, monkeypatch):
    # LAB4_CONTRACTS.md: REST and gRPC call the same business functions (stock_logic.py).
    from fastapi.testclient import TestClient
    import main

    monkeypatch.setenv("INVENTORY_GRPC_ENABLED", "0")  # the fixture already runs a gRPC server
    with TestClient(main.app) as rest:
        assert stub.ReserveStock(_items(("3", 3)), timeout=2).success
        assert rest.get("/api/inventory/3").json()["stock"] == 5

        assert rest.post("/api/inventory/release", json={"items": [{"productId": 3, "quantity": 3}]}).status_code == 200
        assert _check(stub, "3", 1).availableQuantity == 8
