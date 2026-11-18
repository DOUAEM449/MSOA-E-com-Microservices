
from pathlib import Path
import sqlite3

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel


# Chemin vers la base de donnees SQLite
BASE_DIR = Path(__file__).resolve().parent
DATABASE_PATH = BASE_DIR / "db" / "catalog.db"


# Application FastAPI
app = FastAPI(
    title="Catalog Microservice",
    description="REST API for e-commerce products",
    version="2.0.0"
)


# Configuration CORS pour React / Vite
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
    allow_methods=["GET"],
    allow_headers=["*"],
)


# Structure d'un produit
class Product(BaseModel):
    id: int
    name: str
    category: str
    price: float
    image: str
    description: str


class Price(BaseModel):
    amount: float
    currency: str


class ProductV2(BaseModel):
    id: int
    name: str
    category: str
    price: Price
    image: str
    description: str


# Connexion SQLite
def get_connection():
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    columns = {
        row["name"]
        for row in connection.execute("PRAGMA table_info(products)")
    }
    if "currency" not in columns:
        connection.execute(
            "ALTER TABLE products ADD COLUMN currency TEXT NOT NULL DEFAULT 'MAD'"
        )
        connection.commit()
    return connection


# GET /products
@app.get("/products", response_model=list[Product])
def get_products():
    connection = get_connection()

    try:
        cursor = connection.cursor()
        cursor.execute(
            "SELECT id, name, category, price, image, description "
            "FROM products ORDER BY id"
        )

        products = cursor.fetchall()
        return [dict(product) for product in products]

    finally:
        connection.close()


# GET /products/{id}
@app.get("/products/{product_id}", response_model=Product)
def get_product_by_id(product_id: int):
    connection = get_connection()

    try:
        cursor = connection.cursor()
        cursor.execute(
            "SELECT id, name, category, price, image, description "
            "FROM products WHERE id = ?",
            (product_id,)
        )
        product = cursor.fetchone()

        if product is None:
            raise HTTPException(
                status_code=404,
                detail="Product not found"
            )

        return dict(product)

    finally:
        connection.close()


def to_v2(product: dict) -> dict:
    result = dict(product)
    amount = result.pop("price")
    currency = result.pop("currency", "MAD")
    result["price"] = {"amount": amount, "currency": currency}
    return result


# Legacy API contract. Existing frontend and Orders consumers keep receiving
# a numeric price, so this endpoint can be deployed without a coordinated cutover.
@app.get("/api/v1/products", response_model=list[Product])
def get_products_v1():
    return get_products()


@app.get("/api/v1/products/{product_id}", response_model=Product)
def get_product_v1(product_id: int):
    return get_product_by_id(product_id)


# Currency-aware API contract.
@app.get("/api/v2/products", response_model=list[ProductV2])
def get_products_v2():
    connection = get_connection()
    try:
        rows = connection.execute(
            "SELECT id, name, category, price, currency, image, description "
            "FROM products ORDER BY id"
        ).fetchall()
        return [to_v2(dict(row)) for row in rows]
    finally:
        connection.close()


@app.get("/api/v2/products/{product_id}", response_model=ProductV2)
def get_product_v2(product_id: int):
    connection = get_connection()
    try:
        row = connection.execute(
            "SELECT id, name, category, price, currency, image, description "
            "FROM products WHERE id = ?",
            (product_id,),
        ).fetchone()
        if row is None:
            raise HTTPException(
                status_code=404,
                detail="Product not found",
            )
        return to_v2(dict(row))
    finally:
        connection.close()
