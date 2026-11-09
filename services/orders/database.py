import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Generator, Optional, Union


DEFAULT_DATABASE_PATH = Path(__file__).resolve().parent / "db" / "orders.db"
DATABASE_PATH = Path(os.getenv("ORDERS_DB_PATH", str(DEFAULT_DATABASE_PATH)))
DatabasePath = Union[str, Path]


@contextmanager
def get_connection(
    database_path: Optional[DatabasePath] = None,
) -> Generator[sqlite3.Connection, None, None]:
    path = Path(database_path) if database_path is not None else DATABASE_PATH
    connection = sqlite3.connect(path, timeout=10.0)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 10000")
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def initialize_database(database_path: Optional[DatabasePath] = None) -> None:
    path = Path(database_path) if database_path is not None else DATABASE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)

    with get_connection(path) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS orders (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                customer_name TEXT NOT NULL,
                customer_address TEXT NOT NULL,
                customer_city TEXT NOT NULL,
                total REAL NOT NULL,
                status TEXT NOT NULL DEFAULT 'PENDING_PAYMENT',
                created_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS order_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id TEXT NOT NULL,
                product_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                price REAL NOT NULL,
                quantity INTEGER NOT NULL,
                FOREIGN KEY (order_id) REFERENCES orders(id)
            )
            """
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_orders_user_created "
            "ON orders(user_id, created_at DESC)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_order_items_order "
            "ON order_items(order_id)"
        )
