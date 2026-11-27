"""
Lab 5 — Routing table of the gateway (contract: docs/lab5-guide.html §5.1).

The gateway never rewrites paths: /api/orders/123 is sent as /api/orders/123
to the service behind the logical name orders-service.
"""

from typing import List, Optional, Tuple

# (path prefix, logical service name)
ROUTES: List[Tuple[str, str]] = [
    ("/api/auth", "auth-service"),
    ("/products", "catalog-service"),
    ("/api/v1/products", "catalog-service"),
    ("/api/v2/products", "catalog-service"),
    ("/api/inventory", "inventory-service"),
    ("/api/orders", "orders-service"),
    ("/api/payments", "payments-service"),
    ("/api/shipments", "shipping-service"),
    ("/activity", "analytics-service"),            # Problem 3, professor's service
    ("/api/analytics", "events-analytics-service"),  # Lab 4 Kafka analytics
]

# Longest prefix first, so a more specific prefix always wins.
_SORTED = sorted(ROUTES, key=lambda route: len(route[0]), reverse=True)


def match(path: str) -> Optional[str]:
    """
    Return the logical service name for a request path, or None.

    A prefix matches the exact path or the path followed by '/':
    /products and /products/3 match "/products", /productsX does not.
    """
    for prefix, service_name in _SORTED:
        if path == prefix or path.startswith(prefix + "/"):
            return service_name
    return None
