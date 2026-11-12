from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from routes import router as auth_router

app = FastAPI(
    title="Auth Service",
    description="Microservice responsible for authentication, registration and session tokens. "
                "All errors are returned as {\"message\": \"...\"}.",
    version="1.0.0"
)

# إعدادات CORS للسماح لـ React Frontend بالاتصال
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# تسجيل الـ Router
app.include_router(auth_router)


# Error schema shared with the other services: always {"message": "..."}
@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    message = exc.detail if isinstance(exc.detail, str) else "Request failed."
    return JSONResponse(status_code=exc.status_code, content={"message": message}, headers=exc.headers)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = exc.errors()
    first = errors[0] if errors else {}
    field = ".".join(str(p) for p in first.get("loc", ()) if p != "body")
    if first.get("type") == "missing":
        message = f"{field} is required." if field else "All fields are required."
    else:
        message = f"{field}: {first.get('msg', 'invalid value')}" if field else "Invalid request body."
    return JSONResponse(status_code=400, content={"message": message})


@app.exception_handler(Exception)
async def unexpected_exception_handler(request: Request, exc: Exception):
    return JSONResponse(status_code=500, content={"message": "Internal server error."})

@app.get("/")
def health_check():
    return {"service": "Auth Service", "status": "UP", "port": 8081}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8081, reload=True)
