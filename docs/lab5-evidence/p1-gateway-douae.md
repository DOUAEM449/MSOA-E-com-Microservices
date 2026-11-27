# Lab 5 · Problem 1 · Preuves (Douae)

Généré le 2026-11-27T18:53:27Z sur `main` après le merge de la PR #21. Services lancés avec `scripts/start-services.ps1` (gateway démarrée en dernier sur 8080).

## 1. Gateway démarrée (5a)

```http
GET http://127.0.0.1:8080/health
HTTP/1.1 200 OK
server: uvicorn
content-length: 39
content-type: application/json

{"status":"UP","service":"api-gateway"}

```

## 2. Routage statique : direct vs gateway (5b)

| Requête | Service | Direct (port du service) | Via gateway (8080) | Identique |
|---|---|---|---|---|
| `GET /products/1` | catalog-service | 200 `{"id":1,"name":"Lenovo ThinkPad E14","category":"Laptops","p` | 200 `{"id":1,"name":"Lenovo ThinkPad E14","category":"Laptops","p` | oui |
| `GET /api/v1/products` | catalog-service | 200 `[{"id":1,"name":"Lenovo ThinkPad E14","category":"Laptops","` | 200 `[{"id":1,"name":"Lenovo ThinkPad E14","category":"Laptops","` | oui |
| `GET /api/v2/products/2` | catalog-service | 200 `{"id":2,"name":"Samsung Galaxy A55","category":"Smartphones"` | 200 `{"id":2,"name":"Samsung Galaxy A55","category":"Smartphones"` | oui |
| `GET /api/inventory/1` | inventory-service | 200 `{"productId":1,"stock":11}` | 200 `{"productId":1,"stock":11}` | oui |
| `GET /api/orders/order-inexistant` | orders-service | 404 `{"message":"Order not found."}` | 404 `{"message":"Order not found."}` | oui |
| `GET /api/payments/order/order-inexistant` | payments-service | 404 `{"message":"No payment found for order order-inexistant"}` | 404 `{"message":"No payment found for order order-inexistant"}` | oui |
| `GET /api/shipments/order/order-inexistant` | shipping-service | 404 `{"message":"No shipment found for order order-inexistant"}` | 404 `{"message":"No shipment found for order order-inexistant"}` | oui |
| `POST /api/auth/login` | auth-service | 401 `{"message":"Invalid email or password."}` | 401 `{"message":"Invalid email or password."}` | oui |
| `POST /api/orders` | orders-service | 400 `{"message":"Validation error (body.userId): Field required"}` | 400 `{"message":"Validation error (body.userId): Field required"}` | oui |
| `GET /api/analytics/summary` | events-analytics-service | 200 `{"totalEvents":0,"totalOrdersTracked":0,"eventsByType":{},"e` | 200 `{"totalEvents":0,"totalOrdersTracked":0,"eventsByType":{},"e` | oui |

## 3. Erreurs propres à la gateway

| Requête | Réponse de la gateway |
|---|---|
| `GET /xyz` (aucune route) | 404 `{"error":"No route for /xyz"}` |
| `GET /activity` (analytics-service sans adresse) | 503 `{"error":"analytics-service is not registered"}` |

## 4. CORS (le frontend sur 5173 peut appeler la gateway)

```http
OPTIONS http://127.0.0.1:8080/api/orders  (Origin: http://localhost:5173)
HTTP/1.1 200 OK
access-control-allow-methods: GET, POST, PATCH, OPTIONS
access-control-max-age: 600
access-control-allow-headers: Accept, Accept-Language, Authorization, Content-Language, Content-Type
access-control-allow-credentials: true
access-control-allow-origin: http://localhost:5173
```

## 5. Tests automatisés

```
26 passed, 1 warning in 2.33s
```
