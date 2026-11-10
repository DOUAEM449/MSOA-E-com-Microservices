
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
    version="1.0.0"
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


# Connexion SQLite
def get_connection():
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
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
