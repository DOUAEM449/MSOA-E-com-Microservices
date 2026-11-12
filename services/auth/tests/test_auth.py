import hashlib
import shutil
import sqlite3
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

SERVICE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVICE_DIR))

import database  # noqa: E402
from main import app  # noqa: E402


@pytest.fixture
def db_path(tmp_path, monkeypatch):
    path = tmp_path / "auth.db"
    conn = sqlite3.connect(path)
    conn.executescript((SERVICE_DIR / "db" / "schema.sql").read_text(encoding="utf-8"))
    conn.executescript((SERVICE_DIR / "db" / "seed.sql").read_text(encoding="utf-8"))
    conn.commit()
    conn.close()
    monkeypatch.setattr(database, "DB_PATH", str(path))
    return path


@pytest.fixture
def client(db_path):
    return TestClient(app)


def _stored_hash(db_path, email):
    conn = sqlite3.connect(db_path)
    try:
        return conn.execute("SELECT password_hash FROM users WHERE email = ?", (email,)).fetchone()[0]
    finally:
        conn.close()


def test_register_stores_salted_bcrypt_hash(client, db_path):
    for email in ("a@test.local", "b@test.local"):
        r = client.post("/api/auth/register", json={"name": "A", "email": email, "password": "Secret123"})
        assert r.status_code == 201

    h1 = _stored_hash(db_path, "a@test.local")
    h2 = _stored_hash(db_path, "b@test.local")
    assert h1.startswith("$2b$")
    assert "Secret123" not in h1
    assert h1 != h2  # same password, different salt


def test_login_success_and_wrong_password(client):
    client.post("/api/auth/register", json={"name": "A", "email": "a@test.local", "password": "Secret123"})

    ok = client.post("/api/auth/login", json={"email": "a@test.local", "password": "Secret123"})
    assert ok.status_code == 200
    assert ok.json()["user"]["email"] == "a@test.local"
    assert ok.json()["token"]

    bad = client.post("/api/auth/login", json={"email": "a@test.local", "password": "wrong"})
    assert bad.status_code == 401


def test_demo_account_from_seed(client):
    r = client.post("/api/auth/login", json={"email": "demo@msoa.shop", "password": "demo123"})
    assert r.status_code == 200
    bad = client.post("/api/auth/login", json={"email": "demo@msoa.shop", "password": "nope"})
    assert bad.status_code == 401


def test_legacy_sha256_hash_is_upgraded_on_login(client, db_path):
    legacy = hashlib.sha256(b"OldPass1").hexdigest()
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO users VALUES ('old-1','Old','old@test.local',?,'CUSTOMER','2026-01-01T00:00:00Z')",
        (legacy,),
    )
    conn.commit()
    conn.close()

    assert client.post("/api/auth/login", json={"email": "old@test.local", "password": "bad"}).status_code == 401
    assert _stored_hash(db_path, "old@test.local") == legacy

    r = client.post("/api/auth/login", json={"email": "old@test.local", "password": "OldPass1"})
    assert r.status_code == 200
    upgraded = _stored_hash(db_path, "old@test.local")
    assert upgraded.startswith("$2b$")

    again = client.post("/api/auth/login", json={"email": "old@test.local", "password": "OldPass1"})
    assert again.status_code == 200


def test_password_longer_than_72_bytes_is_rejected(client):
    r = client.post("/api/auth/register", json={"name": "A", "email": "long@test.local", "password": "x" * 73})
    assert r.status_code == 400
