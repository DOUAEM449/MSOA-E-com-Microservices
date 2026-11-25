import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from database import init_db
from consumer import start_consumer, stop_consumer
from routes import router

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    start_consumer()
    logging.info("Analytics Service started")

    yield

    stop_consumer()
    logging.info("Analytics Service stopped")


app = FastAPI(
    title="Analytics Service",
    version="1.0.0",
    description="Kafka-based e-commerce analytics service",
    lifespan=lifespan
)

app.include_router(router)


@app.get("/")
def home():
    return {"service": "Analytics Service", "status": "UP"}


@app.get("/health")
def health():
    return {"status": "UP"}
