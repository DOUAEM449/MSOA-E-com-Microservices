# Shipping Service

| Property | Value |
|----------|-------|
| **Port** | 8086 |
| **Owner** | Imane |
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

The detailed contract is available in [API_CONTRACT.md](API_CONTRACT.md).

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ORDERS_URL` | `http://localhost:8084` | URL of the Orders service |
| `RABBITMQ_URL` | `amqp://guest:guest@localhost:5672/%2F` | RabbitMQ connection URI |

## Business rules

- Only `PAID` orders can have a shipment created
- Creating a shipment returns `201`. Repeating the request returns the current shipment with `200`.
- Status transitions (sequential only): `PREPARING → SHIPPED → IN_TRANSIT → DELIVERED`
- Skipping a step or going backward → 409
- Before each status change, Shipping asks Orders for the order; a `CANCELLED` order → 409 (shipment stays as it is)
- If Orders service is unavailable → 503
- Errors are always JSON `{"message": "..."}`; invalid or missing fields → 400

## RabbitMQ

FastAPI starts the consumer in a dedicated thread and closes its connection on shutdown.
The consumer reads `ShipmentRequested` from the durable `shipping_requests` queue
using manual acknowledgments and a prefetch of one. It shares the same creation
function as the HTTP endpoint. SQLite's unique order constraint resolves simultaneous
requests. A replay can return the stored shipment even when Orders is unavailable.

Shipping acknowledges after SQLite commits or confirms an existing shipment.
Invalid payloads and business rejections for absent or unpaid orders are logged
and rejected without requeue. On temporary errors such as Orders being unreachable
or a SQLite lock, the consumer closes the connection with the delivery still
unacked. RabbitMQ can then redeliver it. Shipping reconnects after three seconds.

See [H3.md](H3.md) for the PowerShell commands and evidence to collect.
