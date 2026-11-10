from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from routes import router

app = FastAPI(title="Shipping Service", version="1.0.0")

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


# ── Custom error handler — always return JSON ────────────
@app.exception_handler(Exception)
async def generic_exception_handler(request, exc):
    return JSONResponse(
        status_code=500,
        content={"message": "Internal server error"},
    )


# ── Run ──────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn

    print("[shipping] Starting on port 8086...")
    uvicorn.run(app, host="0.0.0.0", port=8086)

