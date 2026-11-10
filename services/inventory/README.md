# Inventory Microservice

## 1. Description

Inventory is a REST microservice responsible for managing
product stock in the E-commerce application.

## 2. Technologies

- Python
- FastAPI
- SQLite
- Pydantic
- Pytest

## 3. Configuration

Port: 8083

Database: db/inventory.db

## 4. Installation

```bash
python -m pip install -r requirements.txt
```

## 5. Start the service

```bash
python -m uvicorn main:app --reload --port 8083
```

## 6. API Documentation

http://localhost:8083/docs

## 7. REST Endpoints

| Method | Endpoint                   |
| ------ | -------------------------- |
| GET    | /api/inventory/{productId} |
| POST   | /api/inventory/check       |
| POST   | /api/inventory/reserve     |
| POST   | /api/inventory/release     |

## 8. Testing

```bash
python -m pytest -v
```

## 9. Communication

Inventory communicates with Orders through HTTP REST
requests using JSON.

## 10. Main features

- Stock consultation
- Stock availability verification
- Atomic stock reservation
- Stock release after authorized cancellation
- CORS configuration
