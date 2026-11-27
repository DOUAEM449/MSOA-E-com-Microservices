"""
Lab 5 — Gateway configuration (Externalized Configuration, 12-Factor).

Every value can be overridden with an environment variable, so the same code
runs on any machine without being edited.
"""

import os
from typing import Dict

GATEWAY_PORT = int(os.getenv("GATEWAY_PORT", "8080"))

# Timeout for one call from the gateway to a backend service (seconds).
UPSTREAM_TIMEOUT = float(os.getenv("GATEWAY_UPSTREAM_TIMEOUT", "5"))

# Problem 1 (static version): logical service name -> fixed address.
# Override one with <NAME>_URL, e.g. CATALOG_SERVICE_URL=http://127.0.0.1:9192
# Problem 2 replaces this table with the service registry.
DEFAULT_SERVICES: Dict[str, str] = {
    "auth-service": "http://127.0.0.1:8081",
    "catalog-service": "http://127.0.0.1:8082",
    "inventory-service": "http://127.0.0.1:8083",
    "orders-service": "http://127.0.0.1:8084",
    "payments-service": "http://127.0.0.1:8085",
    "shipping-service": "http://127.0.0.1:8086",
    "events-analytics-service": "http://127.0.0.1:8087",
}

# The professor's Analytics service (Problem 3) has no fixed port yet:
# it is only added when ANALYTICS_SERVICE_URL is set.
OPTIONAL_SERVICES = ("analytics-service",)


def env_key(service_name: str) -> str:
    """catalog-service -> CATALOG_SERVICE_URL"""
    return service_name.upper().replace("-", "_") + "_URL"


def static_services() -> Dict[str, str]:
    """Return the static address table, with environment overrides applied."""
    services = {
        name: os.getenv(env_key(name), address).rstrip("/")
        for name, address in DEFAULT_SERVICES.items()
    }
    for name in OPTIONAL_SERVICES:
        address = os.getenv(env_key(name))
        if address:
            services[name] = address.rstrip("/")
    return services
