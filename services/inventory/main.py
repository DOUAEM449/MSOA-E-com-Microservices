
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List

from database import get_connection, initialize_database


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
    allow_origins=["http://localhost:5173"],
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

def aggregate_items(items):
    quantities = {}

    for item in items:
        quantities[item.productId] = (
            quantities.get(item.productId, 0)
            + item.quantity
        )

    return quantities


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

    conn = get_connection()

    try:
        product = conn.execute(
            "SELECT * FROM stock WHERE product_id = ?",
            (productId,)
        ).fetchone()

        if product is None:
            raise HTTPException(
                status_code=404,
                detail="Product not found"
            )

        return {
            "productId": product["product_id"],
            "stock": product["quantity"]
        }

    finally:
        conn.close()


# =====================================
# 7. CHECK STOCK AVAILABILITY
# =====================================

@app.post("/api/inventory/check")
def check_inventory(request: InventoryRequest):

    quantities = aggregate_items(request.items)
    conn = get_connection()

    try:
        for product_id, requested in quantities.items():

            product = conn.execute(
                "SELECT quantity FROM stock WHERE product_id = ?",
                (product_id,)
            ).fetchone()

            if product is None or product["quantity"] < requested:
                return {"available": False}

        return {"available": True}

    finally:
        conn.close()


# =====================================
# 8. RESERVE STOCK (ATOMIC)
# =====================================

@app.post("/api/inventory/reserve")
def reserve_inventory(request: InventoryRequest):

    quantities = aggregate_items(request.items)
    conn = get_connection()

    try:
        # Start atomic transaction
        conn.execute("BEGIN IMMEDIATE")

        # Check all products before updating anything
        for product_id, requested in quantities.items():

            product = conn.execute(
                "SELECT quantity FROM stock WHERE product_id = ?",
                (product_id,)
            ).fetchone()

            if product is None or product["quantity"] < requested:

                conn.execute("ROLLBACK")

                raise HTTPException(
                    status_code=409,
                    detail=f"Insufficient stock for product {product_id}"
                )

        # Update all stock quantities
        for product_id, requested in quantities.items():

            conn.execute("""
                UPDATE stock
                SET quantity = quantity - ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE product_id = ?
            """, (requested, product_id))

        # Confirm transaction
        conn.execute("COMMIT")

        return {"success": True}

    except HTTPException:
        raise

    except Exception:
        if conn.in_transaction:
            conn.execute("ROLLBACK")

        raise HTTPException(
            status_code=500,
            detail="Internal inventory error"
        )

    finally:
        conn.close()


# =====================================
# 9. RELEASE STOCK
# =====================================

@app.post("/api/inventory/release")
def release_inventory(request: InventoryRequest):

    quantities = aggregate_items(request.items)
    conn = get_connection()

    try:
        conn.execute("BEGIN IMMEDIATE")

        # Check that all products exist
        for product_id in quantities:

            product = conn.execute(
                "SELECT product_id FROM stock WHERE product_id = ?",
                (product_id,)
            ).fetchone()

            if product is None:

                conn.execute("ROLLBACK")

                raise HTTPException(
                    status_code=404,
                    detail=f"Product {product_id} not found"
                )

        # Restore stock quantities
        for product_id, quantity in quantities.items():

            conn.execute("""
                UPDATE stock
                SET quantity = quantity + ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE product_id = ?
            """, (quantity, product_id))

        conn.execute("COMMIT")

        return {"success": True}

    except HTTPException:
        raise

    except Exception:
        if conn.in_transaction:
            conn.execute("ROLLBACK")

        raise HTTPException(
            status_code=500,
            detail="Internal inventory error"
        )

    finally:
        conn.close()


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
