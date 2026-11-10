
import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_DIR = BASE_DIR / "db"
DB_PATH = DB_DIR / "inventory.db"


def get_connection():
    conn = sqlite3.connect(
        str(DB_PATH),
        timeout=10,
        isolation_level=None
    )
    conn.row_factory = sqlite3.Row
    return conn


def initialize_database():
    DB_DIR.mkdir(parents=True, exist_ok=True)

    conn = get_connection()

    try:
        schema_path = DB_DIR / "schema.sql"
        seed_path = DB_DIR / "seed.sql"

        # Create database table
        conn.executescript(
            schema_path.read_text(encoding="utf-8")
        )

        # Initialize stock only for missing products
        conn.executescript(
            seed_path.read_text(encoding="utf-8")
        )

    finally:
        conn.close()
