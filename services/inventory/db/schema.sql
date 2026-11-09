PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS stock (
    product_id INTEGER PRIMARY KEY,
    quantity INTEGER NOT NULL CHECK (quantity >= 0),
    updated_at TEXT NOT NULL
);