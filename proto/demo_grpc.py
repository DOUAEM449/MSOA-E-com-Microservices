"""LAB 4 demo: Orders <-> Inventory over gRPC, and REST vs gRPC latency.

Start Catalog (8082), Inventory (8083 + gRPC 50051) and Orders (8084) first, then:
  python proto/demo_grpc.py            # scenarios + benchmark
  python proto/demo_grpc.py --bench 2000
"""
import argparse
import json
import statistics
import sys
import time
from pathlib import Path

import grpc
import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "services" / "inventory"))
import inventory_pb2  # noqa: E402
import inventory_pb2_grpc  # noqa: E402

GRPC_ADDR = "127.0.0.1:50051"
INVENTORY_REST = "http://127.0.0.1:8083"
ORDERS = "http://127.0.0.1:8084"


def title(text):
    print(f"\n=== {text} ===")


def grpc_check(stub, product_id, quantity):
    try:
        r = stub.CheckAvailability(
            inventory_pb2.AvailabilityRequest(productId=product_id, quantity=quantity), timeout=2)
        return {"available": r.available, "availableQuantity": r.availableQuantity}
    except grpc.RpcError as e:
        return {"status": e.code().name, "message": e.details()}


def scenarios(stub):
    title("1. CheckAvailability over gRPC (handout step 4)")
    for product_id, qty, label in [("3", 3, "sufficient stock"), ("3", 10_000, "insufficient stock"),
                                   ("999", 2, "unknown product"), ("3", 0, "invalid quantity")]:
        print(f"  {label:<20} productId={product_id} quantity={qty:<6} -> {grpc_check(stub, product_id, qty)}")

    title("2. Place an order through Orders (REST) -> Orders calls Inventory via gRPC")
    order = {"userId": "demo-grpc", "customer": {"name": "Demo", "address": "1 rue", "city": "Casablanca"},
             "items": [{"productId": 3, "quantity": 2}]}
    before = grpc_check(stub, "3", 1)["availableQuantity"]
    r = httpx.post(f"{ORDERS}/api/orders", json=order, timeout=10)
    print(f"  POST /api/orders (2 x product 3) -> {r.status_code} status={r.json().get('status')}")
    after = grpc_check(stub, "3", 1)["availableQuantity"]
    print(f"  stock of product 3: {before} -> {after}  (reserved via gRPC ReserveStock)")

    if r.status_code == 201:
        c = httpx.post(f"{ORDERS}/api/orders/{r.json()['id']}/cancel", timeout=10)
        print(f"  POST /cancel -> {c.status_code} status={c.json().get('status')}")
        print(f"  stock of product 3 after cancel: {grpc_check(stub, '3', 1)['availableQuantity']}  (ReleaseStock)")

    title("3. Order with insufficient stock -> rejected, nothing reserved")
    order["items"][0]["quantity"] = 10_000
    r = httpx.post(f"{ORDERS}/api/orders", json=order, timeout=10)
    print(f"  POST /api/orders (10000 x product 3) -> {r.status_code} {json.dumps(r.json())}")


def bench(stub, n):
    title(f"4. Latency: {n} availability checks, REST/JSON vs gRPC/Protobuf")
    body = {"items": [{"productId": 3, "quantity": 1}]}
    with httpx.Client() as client:  # keep-alive, the fairest REST case
        for _ in range(20):
            client.post(f"{INVENTORY_REST}/api/inventory/check", json=body)
        rest = []
        for _ in range(n):
            t = time.perf_counter()
            client.post(f"{INVENTORY_REST}/api/inventory/check", json=body).raise_for_status()
            rest.append((time.perf_counter() - t) * 1000)
    req = inventory_pb2.AvailabilityRequest(productId="3", quantity=1)
    for _ in range(20):
        stub.CheckAvailability(req)
    grpc_ms = []
    for _ in range(n):
        t = time.perf_counter()
        stub.CheckAvailability(req, timeout=2)
        grpc_ms.append((time.perf_counter() - t) * 1000)

    rest_size = len(json.dumps(body).encode()) + len(b'{"available":true}')
    grpc_size = len(req.SerializeToString()) + len(
        inventory_pb2.AvailabilityResponse(available=True, availableQuantity=8).SerializeToString())

    def p95(values):
        return sorted(values)[int(len(values) * 0.95) - 1]

    print(f"  {'':<14}{'mean ms':>10}{'median ms':>11}{'p95 ms':>9}{'payload B':>11}")
    for name, values, size in [("REST (JSON)", rest, rest_size), ("gRPC (proto)", grpc_ms, grpc_size)]:
        print(f"  {name:<14}{statistics.mean(values):>10.2f}{statistics.median(values):>11.2f}"
              f"{p95(values):>9.2f}{size:>11}")
    print(f"  gRPC is {statistics.mean(rest) / statistics.mean(grpc_ms):.1f}x faster on average")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bench", type=int, default=500, help="number of calls per protocol")
    args = parser.parse_args()
    with grpc.insecure_channel(GRPC_ADDR) as channel:
        stub = inventory_pb2_grpc.InventoryServiceStub(channel)
        scenarios(stub)
        bench(stub, args.bench)


if __name__ == "__main__":
    main()
