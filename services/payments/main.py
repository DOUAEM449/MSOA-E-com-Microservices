import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

import httpx
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from database import DATABASE_PATH, DatabasePath, initialize_database
from schemas import PaymentCreate
import payments_service

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)


def create_app(
    database_path: Optional[DatabasePath] = None,
    orders_url: Optional[str] = None,
    http_transport: Optional[httpx.AsyncBaseTransport] = None,
) -> FastAPI:
    resolved_database_path = Path(database_path or DATABASE_PATH)
    resolved_orders_url = (orders_url or os.getenv(
        "ORDERS_URL", "http://127.0.0.1:8084"
    )).rstrip("/")

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        initialize_database(resolved_database_path)
        application.state.database_path = resolved_database_path
        application.state.orders_url = resolved_orders_url
        application.state.http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(5.0, connect=2.0),
            limits=httpx.Limits(max_connections=100, max_keepalive_connections=20),
            transport=http_transport,
        )
        try:
            yield
        finally:
            await application.state.http_client.aclose()

    application = FastAPI(
        title="Payments Service",
        description="Processes payments for customer orders.",
        version="1.0.0",
        lifespan=lifespan,
    )

    # ── CORS ─────────────────────────────────────────────────
    application.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",
            "http://localhost:5174",
            "http://localhost:5175",
            "http://127.0.0.1:5173",
            "http://127.0.0.1:5174",
            "http://127.0.0.1:5175",
        ],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization"],
    )

    # ── Error handlers — always return {"message": "..."} ─────
    @application.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        _request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        first = exc.errors()[0] if exc.errors() else {}
        field = ".".join(str(p) for p in first.get("loc", ()) if p != "body")
        message = first.get("msg", "Invalid request")
        return JSONResponse(
            status_code=400,
            content={"message": f"{field}: {message}" if field else message},
        )

    @application.exception_handler(StarletteHTTPException)
    async def http_exception_handler(
        _request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        message = exc.detail if isinstance(exc.detail, str) else "Request failed"
        return JSONResponse(
            status_code=exc.status_code,
            content={"message": message},
            headers=exc.headers,
        )

    @application.exception_handler(Exception)
    async def generic_exception_handler(
        _request: Request, exc: Exception
    ) -> JSONResponse:
        logger.error(
            "Unhandled request error",
            exc_info=(type(exc), exc, exc.__traceback__),
        )
        return JSONResponse(
            status_code=500,
            content={"message": "Internal server error"},
        )

    # ── Routes ───────────────────────────────────────────────

    @application.get("/")
    async def root() -> dict:
        return {"service": "Payments Service", "status": "UP", "port": _configured_port()}

    @application.get("/health")
    async def health() -> dict:
        return {"status": "UP"}

    @application.get("/api/payments")
    async def list_payments() -> list:
        return payments_service.list_payments(application.state.database_path)

    @application.get("/api/payments/order/{order_id}")
    async def get_payment_by_order(order_id: str) -> dict:
        payment = payments_service.get_payment_by_order(
            application.state.database_path, order_id
        )
        if not payment:
            return JSONResponse(
                status_code=404,
                content={"message": f"No payment found for order {order_id}"},
            )
        return payment

    @application.post("/api/payments", status_code=201)
    async def create_payment(body: PaymentCreate) -> dict:
        if not body.orderId or not body.orderId.strip():
            return JSONResponse(
                status_code=400, content={"message": "orderId is required"}
            )
        if not body.method or not body.method.strip():
            return JSONResponse(
                status_code=400, content={"message": "method is required"}
            )

        payment, error = await payments_service.create_payment(
            application.state.database_path,
            application.state.http_client,
            application.state.orders_url,
            body.orderId.strip(),
            body.method.strip(),
        )

        if error:
            status_code, detail = error
            return JSONResponse(status_code=status_code, content=detail)

        return payment

    return application


def _configured_port() -> int:
    try:
        port = int(os.getenv("PORT", "8085"))
    except ValueError as exc:
        raise RuntimeError("PORT must be an integer between 1 and 65535.") from exc
    if not 1 <= port <= 65535:
        raise RuntimeError("PORT must be an integer between 1 and 65535.")
    return port


app = create_app()


if __name__ == "__main__":
    import uvicorn

    print("[payments] Starting on port 8085...")
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=_configured_port(),
        reload=False,
    )
