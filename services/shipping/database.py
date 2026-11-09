import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "db", "shipping.db")


def get_db():
    """Return a SQLite connection with Row factory enabled."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

