# Catalog Microservice

## General Information

- **Port:** 8082
- **Owner:** Salma El Ouarrate
- **Stack:** Python, FastAPI, SQLite
- **Database:** `db/catalog.db`

The Catalog microservice is responsible for managing and exposing product information in the e-commerce application.

It operates independently and uses its own SQLite database.

## Project Structure

```text
catalog/
├── db/
│   ├── catalog.db
│   ├── schema.sql
│   └── seed.sql
├── main.py
├── requirements.txt
└── README.md
```

## Installation

From the repository root:

```powershell
py -3.12 -m venv services\catalog\.venv

.\services\catalog\.venv\Scripts\Activate.ps1

python -m pip install -r services\catalog\requirements.txt
```

## Run the Service

From the repository root, with the virtual environment activated:

```powershell
python -m uvicorn main:app --app-dir services/catalog --host 127.0.0.1 --port 8082 --reload
```

The service is available at:

- API: http://localhost:8082
- Swagger documentation: http://localhost:8082/docs

## REST API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/products` | Retrieve all products |
| GET | `/products/{product_id}` | Retrieve a product by ID |

### Versioned API evolution

| Contract | Endpoint |
|---|---|
| Legacy v1 | `GET /api/v1/products` and `GET /api/v1/products/{product_id}` |
| Currency-aware v2 | `GET /api/v2/products` and `GET /api/v2/products/{product_id}` |

The legacy endpoint remains available and returns a numeric `price`:

```json
{"id": 1, "name": "Lenovo ThinkPad E14", "category": "Laptops", "price": 8499, "image": "", "description": "Reliable 14-inch business laptop"}
```

The v2 endpoint returns an object containing the amount and ISO currency code:

```json
{"id": 1, "name": "Lenovo ThinkPad E14", "category": "Laptops", "price": {"amount": 8499, "currency": "MAD"}, "image": "", "description": "Reliable 14-inch business laptop"}
```

### Error format

```json
{"detail": "Product not found"}
```

- `200 OK`: successful read
- `404 Not Found`: product ID does not exist
- `422 Unprocessable Entity`: invalid path parameter

The API returns JSON responses.

Each product contains:

- `id`
- `name`
- `category`
- `price`
- `image`
- `description`

If a product does not exist, the API returns HTTP 404.

## Database

The service uses SQLite through Python's built-in `sqlite3` module.

The database contains the products table and is independent of the databases used by other microservices.

## Frontend Integration

The React frontend communicates with the Catalog service through REST API calls.

The backend configuration is defined in:

`src/config/backend.js`

The Catalog mode must be set to:

```javascript
CATALOG: "rest"
```

The frontend accesses the service at:

`http://localhost:8082`

CORS is configured to allow the React development server.

## Architecture

The Catalog service is an independent microservice responsible only for product catalogue operations.

It exposes its functionality through HTTP REST endpoints and exchanges JSON data with the frontend.