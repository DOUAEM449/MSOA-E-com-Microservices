# Payments Service

| Property     | Value                          |
|--------------|--------------------------------|
| **Port**     | 8085                           |
| **Owner**    | Taha                           |
| **Stack**    | Python 3 · FastAPI · SQLite    |
| **Database** | `db/payments.db`               |

## Endpoints

| Method | Path                            | Description                                 |
|--------|---------------------------------|---------------------------------------------|
| GET    | `/api/payments`                 | List all payments                           |
| GET    | `/api/payments/order/{orderId}` | Get payment by order ID                     |
| POST   | `/api/payments`                 | Create a payment `{"orderId","method"}`     |
| GET    | `/health`                       | Health check                                |

## How to run

```bash
cd services/payments
pip install -r requirements.txt
python main.py
```

The service starts on **http://localhost:8085**.

The detailed contract is available in [API_CONTRACT.md](API_CONTRACT.md).

## Run tests

```bash
cd services/payments
python -m pytest tests/ -v
```

## Postman

Import `postman/payments.postman_collection.json` into Postman.
Set the `orderId` variable to a valid `PENDING_PAYMENT` order ID before running the "Create payment - 201 success" request.

## Environment variables

| Variable     | Default                    | Description               |
|--------------|----------------------------|---------------------------|
| `ORDERS_URL` | `http://localhost:8084`    | URL of the Orders service |

## Business rules

- Payment reads the order total from Orders service (never from frontend)
- Only orders with status `PENDING_PAYMENT` can be paid
- Duplicate payment for the same order → 409
- After a successful payment, the order status is updated to `PAID`
- If that update fails, the payment is deleted again (compensation) and an error is returned (409 / 502 / 503)
- If Orders service is unavailable → 503
- Errors are always JSON `{"message": "..."}`; invalid or missing fields → 400
