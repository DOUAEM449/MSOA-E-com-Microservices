import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

import httpx
from fastapi import FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from database import DATABASE_PATH, DatabasePath, initialize_database
from schemas import CreateOrderInput, OrderStatus, UpdateStatusInput
from service import (
    cancel_order,
    create_order,
    get_order,
    get_orders,
    update_order_status,
)


logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)


def create_app(
    database_path: Optional[DatabasePath] = None,
    catalog_url: Optional[str] = None,
    inventory_url: Optional[str] = None,
    http_transport: Optional[httpx.AsyncBaseTransport] = None,
) -> FastAPI:
    resolved_database_path = Path(database_path or DATABASE_PATH)
    resolved_catalog_url = (catalog_url or os.getenv(
        "CATALOG_URL", "http://localhost:8082"
    )).rstrip("/")
    resolved_inventory_url = (inventory_url or os.getenv(
        "INVENTORY_URL", "http://localhost:8083"
    )).rstrip("/")

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        initialize_database(resolved_database_path)
        app.state.database_path = resolved_database_path
        app.state.catalog_url = resolved_catalog_url
        app.state.inventory_url = resolved_inventory_url
        app.state.http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(5.0, connect=2.0),
            limits=httpx.Limits(max_connections=100, max_keepalive_connections=20),
            transport=http_transport,
        )
        try:
            yield
        finally:
            await app.state.http_client.aclose()

    application = FastAPI(
        title="Orders Service",
        description="Creates and manages customer orders.",
        version="1.0.0",
        lifespan=lifespan,
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173"],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization"],
    )

    @application.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        _request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        first_error = exc.errors()[0] if exc.errors() else {}
        location = ".".join(str(part) for part in first_error.get("loc", ()))
        message = first_error.get("msg", "Invalid request.")
        suffix = f" ({location})" if location else ""
        return JSONResponse(
            status_code=400,
            content={"message": f"Validation error{suffix}: {message}"},
        )

    @application.exception_handler(StarletteHTTPException)
    async def http_exception_handler(
        _request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        message = exc.detail if isinstance(exc.detail, str) else "Request failed."
        return JSONResponse(
            status_code=exc.status_code,
            content={"message": message},
            headers=exc.headers,
        )

    @application.exception_handler(Exception)
    async def unexpected_exception_handler(
        _request: Request, exc: Exception
    ) -> JSONResponse:
        logger.error(
            "Unhandled request error",
            exc_info=(type(exc), exc, exc.__traceback__),
        )
        return JSONResponse(
            status_code=500,
            content={"message": "An unexpected server error occurred."},
        )

    @application.get("/")
    async def health_check() -> dict:
        return {"service": "Orders Service", "status": "UP", "port": _configured_port()}

    @application.get("/health")
    async def health() -> dict:
        return {"status": "UP"}

    @application.get("/api/orders")
    async def list_orders(user_id: str = Query(alias="userId", min_length=1)) -> list:
        return get_orders(application.state.database_path, user_id.strip())

    @application.get("/api/orders/{order_id}")
    async def read_order(order_id: str) -> dict:
        return get_order(application.state.database_path, order_id)

    @application.post("/api/orders", status_code=201)
    async def post_order(payload: CreateOrderInput) -> dict:
        return await create_order(
            application.state.database_path,
            application.state.http_client,
            application.state.catalog_url,
            application.state.inventory_url,
            payload,
        )

    @application.patch("/api/orders/{order_id}/status")
    async def patch_order_status(
        order_id: str, payload: UpdateStatusInput
    ) -> dict:
        return await update_order_status(
            application.state.database_path,
            application.state.http_client,
            application.state.inventory_url,
            order_id,
            OrderStatus(payload.status),
        )

    @application.post("/api/orders/{order_id}/cancel")
    async def post_cancel_order(order_id: str) -> dict:
        return await cancel_order(
            application.state.database_path,
            application.state.http_client,
            application.state.inventory_url,
            order_id,
        )

    return application


def _configured_port() -> int:
    try:
        port = int(os.getenv("PORT", "8084"))
    except ValueError as exc:
        raise RuntimeError("PORT must be an integer between 1 and 65535.") from exc
    if not 1 <= port <= 65535:
        raise RuntimeError("PORT must be an integer between 1 and 65535.")
    return port


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=_configured_port(),
        reload=False,
    )
