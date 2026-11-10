# Payments Service

| Property | Value |
|----------|-------|
| **Port** | 8085 |
| **Owner** | Taha |
| **Stack** | Python 3 · FastAPI · SQLite |
| **Database** | `db/payments.db` |

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/payments` | List all payments |
| GET | `/api/payments/order/{orderId}` | Get payment by order ID |
| POST | `/api/payments` | Create a payment `{"orderId","method"}` |
| GET | `/health` | Health check |

## How to run

```bash
cd services/payments
pip install -r requirements.txt
python main.py
```

The service starts on **http://localhost:8085**.

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ORDERS_URL` | `http://localhost:8084` | URL of the Orders service |

## Business rules

- Payment reads the order total from Orders service (never from frontend)
- Only orders with status `PENDING_PAYMENT` can be paid
- Duplicate payment for the same order → 409
- After a successful payment, the order status is updated to `PAID`
- If Orders service is unavailable → 503
