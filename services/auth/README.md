# Auth service

- Port: 8081
- Owner: Youssef
- Stack: Python (FastAPI)
- DB: `db/auth.db` (SQLite, data dyal had service bohdo)

## API contract
- Full contract (endpoints, headers, request/response schemas, errors): [API_CONTRACT.md](API_CONTRACT.md)
- OpenAPI spec: [openapi.json](openapi.json) (live at `/openapi.json`, Swagger UI at `/docs`)
- Postman collection: [postman/auth.postman_collection.json](postman/auth.postman_collection.json)
- All errors use `{"message": "..."}`.

## Password storage
- Passwords are hashed with **bcrypt** (random salt per user, cost 12). They are never stored in clear text.
- Old accounts that still have an unsalted SHA-256 hash can still log in. Their hash is replaced by a bcrypt hash on their next successful login.
- Passwords longer than 72 bytes (bcrypt limit) are rejected with `400`.
- Demo account (from `db/seed.sql`): `demo@msoa.shop` / `demo123`.

## Tests
```bash
pip install -r requirements.txt pytest httpx
python -m pytest -q tests
```

## How to run
```bash
python main.py
```
or
```bash
uvicorn main:app --port 8081 --reload
```

## Interactive API Docs (Swagger)
- http://localhost:8081/docs

L contrat REST: shof `frontend/README.md` et `docs/guide.html`.
