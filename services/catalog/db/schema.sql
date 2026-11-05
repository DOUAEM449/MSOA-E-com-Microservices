PRAGMA foreign_keys = ON;
CREATE TABLE products (id INTEGER PRIMARY KEY, name TEXT NOT NULL, category TEXT NOT NULL, price REAL NOT NULL CHECK(price >= 0), image TEXT NOT NULL DEFAULT '', description TEXT NOT NULL DEFAULT '');
