# Orders service

FastAPI service that creates and manages orders. It owns `db/orders.db` and
coordinates Catalog product lookups and Inventory stock reservations over HTTP.

## Run

```powershell
cd services\orders
python -m pip install -r requirements.txt
python main.py
```

The service listens on `0.0.0.0:8084` by default. Configuration is read from:

| Variable | Default | Description |
| --- | --- | --- |
| `PORT` | `8084` | HTTP listening port |
| `CATALOG_URL` | `http://localhost:8082` | Catalog service base URL |
| `INVENTORY_URL` | `http://localhost:8083` | Inventory service base URL |
| `ORDERS_DB_PATH` | `services/orders/db/orders.db` | Optional SQLite database path |

Interactive API documentation is available at `/docs`.

## API

- `GET /api/orders?userId=<id>` — list a user's orders, newest first.
- `GET /api/orders/{id}` — get an order and its line items.
- `POST /api/orders` — create an order from `{ "userId", "customer", "items" }`.
  The service reads product names and prices from Catalog, reserves stock, then
  saves the order. The client-supplied price is never trusted.
- `PATCH /api/orders/{id}/status` — advance through `PENDING_PAYMENT -> PAID ->
  SHIPPED -> DELIVERED`; set `CANCELLED` only to invoke the cancellation workflow.
- `POST /api/orders/{id}/cancel` — cancel an unshipped order and release its
  reserved inventory.
- `GET /` and `GET /health` — health checks.

All errors use `{"message":"..."}`. Invalid input is returned with HTTP 400;
invalid status transitions and unavailable stock use HTTP 409.

SQLite is initialized at application startup without deleting existing data.
Database writes use transactions and parameterized statements. Catalog and
Inventory calls use an async HTTP client with bounded connection and response
timeouts. Inventory is released if persistence fails after a successful
reservation; a cancellation status is restored if inventory release fails.

The service permits the React development origin `http://localhost:5173` and
only the requested HTTP methods and headers. Authentication/authorization must
be enforced by the API gateway or an agreed token-validation integration; this
service uses the frontend's `userId` query/body contract and does not validate
the Authorization token.

## Tests

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest
```
