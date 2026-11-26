
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List

import logging
import os

import grpc_server
import stock_logic
from database import initialize_database

logger = logging.getLogger("uvicorn.error")  # shown in the uvicorn console


# =====================================
# 1. FASTAPI APPLICATION
# =====================================

app = FastAPI(
    title="Inventory Microservice",
    description="E-commerce Stock Management API",
    version="1.0.0"
)


# =====================================
# 2. CORS CONFIGURATION
# =====================================

app.add_middleware(
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
    allow_methods=["*"],
    allow_headers=["*"]
)


# =====================================
# 3. DATABASE INITIALIZATION
# =====================================

@app.on_event("startup")
def startup():
    initialize_database()
    _start_grpc_server()


# gRPC interface (LAB 4), served next to REST on port 50051 by default.
# Set INVENTORY_GRPC_ENABLED=0 to run REST only.
_grpc_server = None


def _start_grpc_server():
    global _grpc_server
    if os.getenv("INVENTORY_GRPC_ENABLED", "1") == "0":
        return
    try:
        _grpc_server = grpc_server.create_server()
        _grpc_server.start()
        logger.info("Inventory gRPC server listening on port %s", _grpc_server.bound_port)
    except RuntimeError:
        _grpc_server = None
        logger.exception("gRPC server not started; REST API is still available")


@app.on_event("shutdown")
def shutdown():
    if _grpc_server is not None:
        _grpc_server.stop(grace=2)


# =====================================
# 4. REQUEST MODELS
# =====================================

class InventoryItem(BaseModel):
    productId: int = Field(gt=0)
    quantity: int = Field(gt=0)


class InventoryRequest(BaseModel):
    items: List[InventoryItem] = Field(min_length=1)


# =====================================
# 5. GROUP DUPLICATE PRODUCTS
# =====================================
# Business rules are in stock_logic.py, shared with the gRPC server (LAB 4).

def aggregate_items(items):
    return stock_logic.aggregate((item.productId, item.quantity) for item in items)


# =====================================
# 6. GET PRODUCT STOCK
# =====================================

@app.get("/api/inventory/{productId}")
def get_inventory(productId: int):

    if productId <= 0:
        raise HTTPException(
            status_code=400,
            detail="Invalid product ID"
        )

    try:
        stock = stock_logic.get_stock(productId)
    except stock_logic.ProductNotFound:
        raise HTTPException(
            status_code=404,
            detail="Product not found"
        )

    return {
        "productId": productId,
        "stock": stock
    }


# =====================================
# 7. CHECK STOCK AVAILABILITY
# =====================================

@app.post("/api/inventory/check")
def check_inventory(request: InventoryRequest):

    return {"available": stock_logic.is_available(aggregate_items(request.items))}


# =====================================
# 8. RESERVE STOCK (ATOMIC)
# =====================================

@app.post("/api/inventory/reserve")
def reserve_inventory(request: InventoryRequest):

    try:
        stock_logic.reserve(aggregate_items(request.items))
    except stock_logic.InsufficientStock as error:
        raise HTTPException(status_code=409, detail=error.message)
    except Exception:
        logger.exception("Inventory reservation failed")
        raise HTTPException(
            status_code=500,
            detail="Internal inventory error"
        )

    return {"success": True}


# =====================================
# 9. RELEASE STOCK
# =====================================

@app.post("/api/inventory/release")
def release_inventory(request: InventoryRequest):

    try:
        stock_logic.release(aggregate_items(request.items))
    except stock_logic.ProductNotFound as error:
        raise HTTPException(status_code=404, detail=error.message)
    except Exception:
        logger.exception("Inventory release failed")
        raise HTTPException(
            status_code=500,
            detail="Internal inventory error"
        )

    return {"success": True}


# =====================================
# 10. HOME ENDPOINT
# =====================================

@app.get("/")
def home():

    return {
        "message": "Inventory Microservice is running",
        "service": "Inventory",
        "port": 8083
    }
