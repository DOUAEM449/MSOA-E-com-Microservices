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


# ---- API contract: every error uses {"message": str} ----

def _assert_error(response, status_code):
    assert response.status_code == status_code
    body = response.json()
    assert set(body) == {"message"}
    assert isinstance(body["message"], str) and body["message"]


@pytest.mark.parametrize("payload", [
    {"email": "a@test.local", "password": "x"},                  # name missing
    {"name": "A", "password": "x"},                               # email missing
    {"name": "  ", "email": "a@test.local", "password": "x"},    # blank name
    {"name": "A", "email": "a@test.local", "password": ""},     # blank password
    {"name": "A", "email": "not-an-email", "password": "x"},    # invalid e-mail
])
def test_register_invalid_input_returns_400(client, payload):
    _assert_error(client.post("/api/auth/register", json=payload), 400)


def test_register_contract(client):
    r = client.post("/api/auth/register", json={"name": " Ann ", "email": "Ann@Test.Local", "password": "p"})
    assert r.status_code == 201
    body = r.json()
    assert set(body) == {"id", "name", "email", "role"}
    assert body["name"] == "Ann" and body["email"] == "ann@test.local" and body["role"] == "CUSTOMER"
    _assert_error(client.post("/api/auth/register", json={"name": "A", "email": "ann@test.local", "password": "p"}), 409)


def test_login_errors(client):
    _assert_error(client.post("/api/auth/login", json={"email": "demo@msoa.shop"}), 400)
    _assert_error(client.post("/api/auth/login", json={"email": "", "password": "x"}), 400)
    _assert_error(client.post("/api/auth/login", json={"email": "nobody@test.local", "password": "x"}), 401)
    _assert_error(client.post("/api/auth/login", json={"email": "demo@msoa.shop", "password": "bad"}), 401)


def test_session_lifecycle(client):
    login = client.post("/api/auth/login", json={"email": "demo@msoa.shop", "password": "demo123"})
    assert login.status_code == 200
    assert set(login.json()) == {"user", "token"}
    token = login.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    me = client.get("/api/auth/me", headers=headers)
    assert me.status_code == 200 and me.json()["email"] == "demo@msoa.shop"

    out = client.post("/api/auth/logout", headers=headers)
    assert out.status_code == 200 and out.json() == {"success": True}

    _assert_error(client.get("/api/auth/me", headers=headers), 401)
    _assert_error(client.get("/api/auth/me"), 401)
    # logout is idempotent
    assert client.post("/api/auth/logout", headers=headers).json() == {"success": True}


def test_unknown_route_uses_error_schema(client):
    _assert_error(client.get("/api/auth/unknown"), 404)
