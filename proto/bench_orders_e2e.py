"""LAB 4 - end-to-end comparison through POST /api/orders (issue #15, optional item).

Two Orders instances run side by side on the same Catalog and Inventory:
  * gRPC: port 8084 (INVENTORY_TRANSPORT=grpc, the default)
  * REST: port 8094, started with INVENTORY_TRANSPORT=rest
Each iteration creates an order for 1 x product 3 and cancels it, so the stock is
unchanged at the end. Only the POST /api/orders time is measured.

  python proto/bench_orders_e2e.py --n 200
"""
import argparse
import statistics
import time

import httpx

TARGETS = {"gRPC  (8084)": "http://127.0.0.1:8084", "REST  (8094)": "http://127.0.0.1:8094"}
ORDER = {
    "userId": "bench-e2e",
    "customer": {"name": "Bench", "address": "1 rue", "city": "Casablanca"},
    "items": [{"productId": 3, "quantity": 1}],
}


def run(client: httpx.Client, base: str, n: int) -> list:
    timings = []
    for i in range(n + 10):  # 10 warm-up iterations
        start = time.perf_counter()
        r = client.post(f"{base}/api/orders", json=ORDER)
        elapsed = (time.perf_counter() - start) * 1000
        r.raise_for_status()
        client.post(f"{base}/api/orders/{r.json()['id']}/cancel").raise_for_status()
        if i >= 10:
            timings.append(elapsed)
    return timings


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=200)
    args = parser.parse_args()
    print(f"POST /api/orders, {args.n} orders per transport (create + cancel, 1 x product 3)")
    print(f"  {'transport':<14}{'mean ms':>10}{'median ms':>11}{'p95 ms':>9}")
    results = {}
    with httpx.Client(timeout=10) as client:
        for name, base in TARGETS.items():
            t = sorted(run(client, base, args.n))
            results[name] = t
            print(f"  {name:<14}{statistics.mean(t):>10.2f}{statistics.median(t):>11.2f}"
                  f"{t[int(len(t) * 0.95) - 1]:>9.2f}")
    g, r = (statistics.mean(v) for v in results.values())
    print(f"  difference: REST - gRPC = {r - g:.2f} ms per order ({r / g:.2f}x)")


if __name__ == "__main__":
    main()
