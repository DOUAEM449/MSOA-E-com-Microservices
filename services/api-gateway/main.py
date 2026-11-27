"""
Lab 5 — API Gateway (single entry point on port 8080).

The frontend talks only to the gateway. For every request the gateway:
  1. [P3, Salma]  intercepts it and logs the activity to analytics-service,
  2. [P3, Imane]  refuses GET /activity from a non-desktop device (403),
  3. [P1, Douae]  finds the logical service from the path (routes.py),
  4. [P1 static / P2 Amal] resolves that name to an address,
  5. [P1, Youssef] forwards the request unchanged (proxy.py).

Run: python -m uvicorn main:app --host 127.0.0.1 --port 8080
"""

from contextlib import asynccontextmanager
from typing import Dict, Optional

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

import config
import proxy
import routes

ALL_METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"]


def create_app(
    services: Optional[Dict[str, str]] = None,
    transport: Optional[httpx.AsyncBaseTransport] = None,
    timeout: Optional[float] = None,
) -> FastAPI:
    """
    services:  address table (default: config.static_services()).
    transport: lets the tests replace the network with httpx.MockTransport.
    """

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # One shared HTTP client (connection pool) for the proxy and Analytics.
        app.state.http = httpx.AsyncClient(
            timeout=timeout if timeout is not None else config.UPSTREAM_TIMEOUT,
            transport=transport,
            follow_redirects=False,  # a redirect goes back to the client unchanged
        )
        try:
            yield
        finally:
            await app.state.http.aclose()

    app = FastAPI(title="API Gateway", version="1.0.0", lifespan=lifespan)
    app.state.services = dict(services) if services is not None else config.static_services()

    # ── Middlewares (Problem 3) ─────────────────────────────────
    # Starlette runs the LAST added middleware FIRST, so add them in this order:
    #   app.add_middleware(DesktopGuardMiddleware)   # Imane, device.py  (runs 2nd)
    #   app.add_middleware(ActivityMiddleware)       # Salma, activity.py (runs 1st)

    # ── Gateway's own routes (declared BEFORE the catch-all) ────

    @app.get("/health")
    async def health():
        return {"status": "UP", "service": "api-gateway"}

    # Imane (Problem 2): app.include_router(registry.router)  -> /registry/register, /registry/services

    # ── Catch-all: everything else is routed to a service ───────

    @app.api_route("/{path:path}", methods=ALL_METHODS, include_in_schema=False)
    async def gateway(request: Request, path: str):
        service_name = routes.match(request.url.path)
        if service_name is None:
            return JSONResponse(status_code=404, content={"error": f"No route for {request.url.path}"})

        # Static resolution (Problem 1). Amal replaces this with discovery.resolve() (Problem 2).
        base_url = app.state.services.get(service_name)
        if base_url is None:
            return JSONResponse(status_code=503, content={"error": f"{service_name} is not registered"})

        return await proxy.forward(request, base_url, app.state.http)

    return app


app = create_app()
