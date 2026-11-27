# API Gateway (Lab 5)

Single entry point of the platform on **http://127.0.0.1:8080**. The frontend
talks only to the gateway; the gateway routes each request to the right service
without changing it.

## Run

```powershell
.\scripts\setup-services.ps1     # creates services\api-gateway\.venv
.\scripts\start-services.ps1     # starts all services, then the gateway
```

Or alone:

```powershell
cd services\api-gateway
.\.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8080
```

## Routing table

| Prefix | Logical name | Static address |
|---|---|---|
| `/api/auth` | auth-service | http://127.0.0.1:8081 |
| `/products`, `/api/v1/products`, `/api/v2/products` | catalog-service | http://127.0.0.1:8082 |
| `/api/inventory` | inventory-service | http://127.0.0.1:8083 |
| `/api/orders` | orders-service | http://127.0.0.1:8084 |
| `/api/payments` | payments-service | http://127.0.0.1:8085 |
| `/api/shipments` | shipping-service | http://127.0.0.1:8086 |
| `/activity` | analytics-service (professor's service) | `ANALYTICS_SERVICE_URL` |
| `/api/analytics` | events-analytics-service (Lab 4 Kafka) | http://127.0.0.1:8087 |

Paths are not rewritten. Gateway routes: `GET /health`
(Problem 2 adds `/registry/register` and `/registry/services`).

## Configuration (environment variables)

| Variable | Default |
|---|---|
| `GATEWAY_PORT` | 8080 (used by the start script) |
| `GATEWAY_UPSTREAM_TIMEOUT` | 5 seconds |
| `<NAME>_URL`, e.g. `CATALOG_SERVICE_URL` | static address above |

## Errors

| Case | Status | Body |
|---|---|---|
| No route for the path | 404 | `{"error": "No route for /xyz"}` |
| No address for the service | 503 | `{"error": "<name> is not registered"}` |
| Any answer from a service | unchanged | unchanged |

## Tests

```powershell
cd services\api-gateway
.\.venv\Scripts\python.exe -m pytest -q
```
