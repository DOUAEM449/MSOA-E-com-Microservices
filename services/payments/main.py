from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from routes import router

app = FastAPI(title="Payments Service", version="1.0.0")

# ── CORS ─────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
    allow_credentials=True,
)

# ── Routes ───────────────────────────────────────────────
app.include_router(router)


@app.get("/health")
def health():
    return {"status": "UP"}


# ── Error handlers — always return {"message": "..."} ─────
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    """Missing/invalid fields → 400 {"message"} (FastAPI's default is 422 {"detail"})."""
    first = exc.errors()[0] if exc.errors() else {}
    field = ".".join(str(p) for p in first.get("loc", ()) if p != "body")
    message = first.get("msg", "Invalid request")
    return JSONResponse(
        status_code=400,
        content={"message": f"{field}: {message}" if field else message},
    )


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request, exc):
    """Unknown route (404), wrong method (405)… → {"message"} instead of {"detail"}."""
    message = exc.detail if isinstance(exc.detail, str) else "Request failed"
    return JSONResponse(status_code=exc.status_code, content={"message": message}, headers=exc.headers)


@app.exception_handler(Exception)
async def generic_exception_handler(request, exc):
    return JSONResponse(
        status_code=500,
        content={"message": "Internal server error"},
    )


# ── Run ──────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn

    print("[payments] Starting on port 8085...")
    uvicorn.run(app, host="0.0.0.0", port=8085)

