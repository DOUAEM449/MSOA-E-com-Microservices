from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routes import router as auth_router

app = FastAPI(
    title="Auth Service",
    description="Microservice responsible for authentication, registration, session management and JWT/tokens.",
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

@app.get("/")
def health_check():
    return {"service": "Auth Service", "status": "UP", "port": 8081}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8081, reload=True)
