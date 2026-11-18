import sqlite3
import os
from pathlib import Path
from typing import Union

DatabasePath = Union[str, Path]

DATABASE_PATH = os.path.join(os.path.dirname(__file__), "db", "payments.db")

SCHEMA_SQL = """\
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS payments (
    id         TEXT PRIMARY KEY,
    order_id   TEXT NOT NULL UNIQUE,
    amount     REAL NOT NULL CHECK(amount >= 0),
    method     TEXT NOT NULL,
    status     TEXT NOT NULL CHECK(status IN ('SUCCESS','FAILED','PENDING','REFUNDED')),
    created_at TEXT NOT NULL
);
"""


def initialize_database(path: DatabasePath) -> None:
    """Create the payments table if it does not exist."""
    db_path = Path(path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    try:
        conn.executescript(SCHEMA_SQL)
    finally:
        conn.close()


def get_db(path: DatabasePath = DATABASE_PATH) -> sqlite3.Connection:
    """Return a SQLite connection with Row factory enabled."""
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn
