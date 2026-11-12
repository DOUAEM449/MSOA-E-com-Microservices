# Shipping Service

| Property | Value |
|----------|-------|
| **Port** | 8086 |
| **Owner** | Taha |
| **Stack** | Python 3 · FastAPI · SQLite |
| **Database** | `db/shipping.db` |

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/shipments` | List all shipments |
| GET | `/api/shipments/order/{orderId}` | Get shipment by order ID |
| POST | `/api/shipments` | Create a shipment `{"orderId","address":{name,address,city}}` |
| PATCH | `/api/shipments/{id}/status` | Update shipment status |
| GET | `/health` | Health check |

## How to run

```bash
cd services/shipping
pip install -r requirements.txt
python main.py
```

The service starts on **http://localhost:8086**.

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ORDERS_URL` | `http://localhost:8084` | URL of the Orders service |

## Business rules

- Only `PAID` orders can have a shipment created
- Duplicate shipment for the same order → 409
- Status transitions (sequential only): `PREPARING → SHIPPED → IN_TRANSIT → DELIVERED`
- Skipping a step or going backward → 409
- Before each status change, Shipping asks Orders for the order; a `CANCELLED` order → 409 (shipment stays as it is)
- If Orders service is unavailable → 503
- Errors are always JSON `{"message": "..."}`; invalid or missing fields → 400
