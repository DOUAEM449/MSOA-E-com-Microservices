PRAGMA foreign_keys = ON;
CREATE TABLE payments (id TEXT PRIMARY KEY, order_id TEXT NOT NULL UNIQUE, amount REAL NOT NULL CHECK(amount >= 0), method TEXT NOT NULL, status TEXT NOT NULL CHECK(status IN ('SUCCESS','FAILED','PENDING','REFUNDED')), created_at TEXT NOT NULL);
