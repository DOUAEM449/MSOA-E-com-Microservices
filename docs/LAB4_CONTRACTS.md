# Lab 4 — Communication contracts

These are the three contracts agreed by the team before writing any code.
**Do not change a contract alone**: the owners on both sides must agree, then update this file.

| Mechanism | Sender | Receiver | Contract | Owners |
|---|---|---|---|---|
| gRPC (sync) | Orders | Inventory | `proto/inventory.proto` | Taha (client), Youssef (server) |
| RabbitMQ (async, queue) | Payments | Shipping | `ShipmentRequested` message (§2) | Douae (producer), Imane (consumer) |
| Kafka (async, event log) | Orders, Payments, Shipping | Analytics | Event envelope (§3) | Salma (producers), Amal (Analytics) |

Existing REST APIs (`docs/API_CONTRACTS.md`) stay unchanged: the frontend keeps using them.

## 0. Infrastructure

Start the brokers once (Docker Desktop must be running):

```powershell
docker compose up -d
docker compose ps
```

| What | Address | Notes |
|---|---|---|
| RabbitMQ (AMQP) | `localhost:5672` | user `guest` / `guest` |
| RabbitMQ web UI | http://localhost:15672 | queues, Ready / Unacked counters |
| Kafka | `localhost:9092` | `bootstrap.servers` for Python clients |
| Kafka web UI | http://localhost:8090 | topics, messages, consumer groups and offsets |
| Inventory gRPC | `127.0.0.1:50051` | started by the Inventory service itself |
| Analytics REST | `127.0.0.1:8087` | new service |

Environment variables (with defaults, so nobody needs a `.env` locally):

| Variable | Default | Used by |
|---|---|---|
| `INVENTORY_GRPC_ENABLED` | `1` (`0` = REST only) | inventory |
| `INVENTORY_GRPC_ADDR` | `127.0.0.1:50051` | orders |
| `INVENTORY_TRANSPORT` | `grpc` (or `rest`) | orders |
| `INVENTORY_GRPC_TIMEOUT` | `2.0` seconds | orders |
| `RABBITMQ_URL` | `amqp://guest:guest@localhost:5672/%2F` | payments, shipping |
| `KAFKA_BOOTSTRAP_SERVERS` | `localhost:9092` | orders, payments, shipping, analytics |
| `KAFKA_TOPIC` | `ecommerce-events` | orders, payments, shipping, analytics |

New Python libraries (already added to each `requirements.txt`; re-run `.\scripts\setup-services.ps1`):

| Library | Services |
|---|---|
| `grpcio`, `protobuf`, `grpcio-tools` | inventory, orders |
| `pika` | payments, shipping |
| `confluent-kafka` | orders, payments, shipping (analytics: Amal adds it) |

The generated gRPC code (`inventory_pb2.py`, `inventory_pb2_grpc.py`) is committed in `services/inventory` and `services/orders`. After changing the `.proto`, regenerate it with `python proto/generate.py` (details in `proto/README.md`).

## 1. gRPC — Orders → Inventory

Full contract: [`proto/inventory.proto`](../proto/inventory.proto).

| RPC | Replaces REST call | When Orders calls it |
|---|---|---|
| `CheckAvailability` | `GET /api/inventory/{productId}` / `POST /api/inventory/check` | checks one product and quantity before the order is accepted |
| `ReserveStock` | `POST /api/inventory/reserve` | when creating an order |
| `ReleaseStock` | `POST /api/inventory/release` | when order creation fails after reserving, or on cancel |

Rules:
- Orders creates **one** gRPC channel at startup and reuses it (like the existing `httpx.AsyncClient`).
- Every call has a **deadline of 2 s** (`INVENTORY_GRPC_TIMEOUT`). `CheckAvailability` is retried once on `UNAVAILABLE`.
- `productId` is a string in the `.proto`, so the same contract works whatever the id format.
- Error mapping on the Orders side: `NOT_FOUND`→404, `FAILED_PRECONDITION`→409, `INVALID_ARGUMENT`→400, `UNAVAILABLE`→503, `DEADLINE_EXCEEDED`→504.
- `INVENTORY_TRANSPORT=rest` switches Orders back to the REST calls (useful for the REST vs gRPC benchmark).
- Inventory REST endpoints stay available (frontend and tests use them). REST and gRPC must call the **same** business functions.

## 2. RabbitMQ — Payments → Shipping

| Setting | Value |
|---|---|
| Exchange | `""` (default exchange) |
| Queue | `shipping_requests` |
| Routing key | `shipping_requests` |
| Queue flags | `durable=True`, `exclusive=False`, `auto_delete=False` |
| Message | `delivery_mode=2` (persistent), `content_type=application/json` |
| Producer | publisher confirms enabled (`channel.confirm_delivery()`) |
| Consumer | `auto_ack=False`, `prefetch_count=1`, ack **after** the shipment is saved |

Both sides declare the queue with exactly these flags (declaration is idempotent).

Message body:

```json
{
  "messageId": "3f6a2c1e-9b7d-4c2a-8e51-0d4b7a9f1c22",
  "type": "ShipmentRequested",
  "orderId": "order-1a2b3c4d",
  "paymentId": "payment-9f8e7d6c",
  "address": {
    "name": "Imane",
    "address": "12 Rue Exemple",
    "city": "Rabat"
  },
  "occurredAt": "2026-11-24T10:15:00Z"
}
```

| Field | Type | Rule |
|---|---|---|
| `messageId` | string (uuid4) | unique per message |
| `type` | string | always `ShipmentRequested` |
| `orderId` | string | order that was paid |
| `paymentId` | string | payment that triggered the request |
| `address.name` / `address.address` / `address.city` | string | taken from the order's `customer` object (Payments already fetches the order) |
| `occurredAt` | string, ISO-8601 UTC | time of publication |

When Payments publishes: right **after** the order was successfully PATCHed to `PAID`. If RabbitMQ is down, the payment still succeeds; Payments logs a warning.

Consumer behaviour (Shipping):
- Valid message, shipment created → `basic_ack`.
- Shipment already exists for `orderId` (duplicate / redelivery) → `basic_ack`, no new shipment (**idempotent**).
- Malformed JSON or missing field → `basic_nack(requeue=False)` and log it (never requeue a message that can never succeed).
- Unexpected error (DB locked, Orders down) → do not ack; RabbitMQ redelivers.
- `POST /api/shipments` also becomes idempotent (returns the existing shipment) because the frontend still calls it after payment.

## 3. Kafka — business events → Analytics

| Setting | Value |
|---|---|
| Topic | `ecommerce-events` (created by `kafka-init`, 3 partitions) |
| Retention | 7 days (`retention.ms=604800000`) |
| Message key | `orderId` (keeps all events of one order in the same partition, in order) |
| Value | JSON envelope below, UTF-8 |
| Analytics consumer group | `analytics-service`, `auto.offset.reset=earliest` |

Envelope (same for every event):

```json
{
  "eventId": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
  "eventType": "OrderCreated",
  "source": "orders",
  "occurredAt": "2026-11-24T10:14:02Z",
  "orderId": "order-1a2b3c4d",
  "data": {}
}
```

Event types and their `data`:

| `eventType` | `source` | Published when | `data` |
|---|---|---|---|
| `OrderCreated` | orders | order saved as `PENDING_PAYMENT` | `{ "userId": "…", "total": 349.0, "itemsCount": 3, "items": [{ "productId": 1, "quantity": 2, "price": 99.5 }] }` |
| `OrderStatusChanged` | orders | status PATCH succeeds | `{ "from": "PENDING_PAYMENT", "to": "PAID" }` |
| `PaymentCompleted` | payments | payment saved and order PAID | `{ "paymentId": "…", "amount": 349.0, "method": "CARD" }` |
| `ShipmentCreated` | shipping | shipment saved | `{ "shipmentId": "…", "trackingNumber": "MSOA-7F3K2A", "city": "Rabat" }` |
| `ShipmentStatusChanged` | shipping | shipment status changes | `{ "shipmentId": "…", "from": "PREPARING", "to": "SHIPPED" }` |

Rules:
- `eventId` is a uuid4; Analytics stores it with a UNIQUE constraint so a redelivered event is counted once.
- Publishing never blocks or fails the HTTP request: if Kafka is down, log a warning and continue.
- Analytics exposes `GET /api/analytics/summary`, `GET /api/analytics/events`, `POST /api/analytics/replay` (resets its offsets to the beginning and rebuilds its stats).

## 4. Tests that prove each requirement

| Requirement | Test |
|---|---|
| High performance (gRPC) | Benchmark 1000 `CheckAvailability`/`ReserveStock` calls (`proto/demo_grpc.py`, or `INVENTORY_TRANSPORT=rest` vs `grpc`) vs 1000 REST calls; report average latency |
| No lost shipments (RabbitMQ) | Handout H3 step 4: normal delivery, Shipping offline (Ready=1), crash before ACK (Unacked→Ready→redelivered) |
| Retention and replay (Kafka) | Create orders while Analytics is stopped, start it, it sees them; call replay, totals are identical |
