# Network Device Management Backend (Flask)

This Flask backend provides RESTful CRUD endpoints for managing network devices and integrates with MongoDB using `pymongo`. It includes schema validation at the MongoDB level, unique indexes, environment-based configuration, and basic logging.

## Features

- RESTful CRUD endpoints:
  - POST /devices (create)
  - GET /devices (list with optional filters)
  - GET /devices/{id} (get by id)
  - PUT /devices/{id} (full replace, idempotent)
  - PATCH /devices/{id} (partial update)
  - DELETE /devices/{id} (delete by id)
- Health check: GET /
- MongoDB integration via `pymongo`
- Collection JSON schema validator and unique indexes on `name` and `ip_address`
- Environment variables with sensible defaults
- Logging with configurable level
- OpenAPI documentation via `flask-smorest` at `/docs`
- Optional async ping utility scaffold (`app/utils/ping.py`)

Legacy endpoints `/device/insert`, `/device/find`, `/device/update`, and `/device/delete` have been removed in favor of RESTful routes.

## Requirements

- Python 3.10+
- MongoDB server reachable per `MONGO_URI`

Install dependencies:

```
pip install -r requirements.txt
```

## Configuration

Copy `.env.example` to `.env` and edit as needed:

```
APP_PORT=3001
LOG_LEVEL=INFO
MONGO_URI=mongodb://localhost:27017
MONGO_DB_NAME=network_devices
MONGO_COLLECTION=devices
```

Sensible defaults are applied if variables are not set.

## Running

From the `BackendContainer` directory:

```
python run.py
```

The API will be available on `http://localhost:3001` and documentation at `http://localhost:3001/docs`.

## REST API Overview

- POST `/devices`
  - Body: `{ "name": "...", "ip_address": "...", "type": "...", "location": "...", "status": "online|offline", "last_ping_time": "ISO-8601" }`
  - Response: `201 { "inserted_id": "<ObjectId as string>" }`
  - Errors: `400` on validation/duplicate, `500` on DB error

- GET `/devices`
  - Query params (optional): `name, ip_address, type, status, location, sort=name:asc, limit, skip`
  - Response: `200 [ Device, ... ]`

- GET `/devices/{id}`
  - Response: `200 Device`
  - Errors: `400` invalid ObjectId, `404` not found

- PUT `/devices/{id}`
  - Body (full document, all required fields): `{ "name": "...", "ip_address": "...", "type": "...", "location": "...", "status": "online|offline", "last_ping_time": "ISO-8601" }`
  - Semantics: Full replace (idempotent). Returns updated device.
  - Responses: `200 Device`, `404` if not found, `400` invalid ObjectId/payload, `409` duplicate key

- PATCH `/devices/{id}`
  - Body (partial): any subset of fields above
  - Responses: `200 Device`, `404` if not found, `400` invalid ObjectId/payload, `409` duplicate key

- DELETE `/devices/{id}`
  - Response: `204` on success (no body) or `404` if not found
  - Errors: `400` invalid ObjectId

All endpoints return JSON error payloads such as:
```
{ "error": "<ErrorType>", "details": "<message or dict>" }
```

## Notes

- The collection validator and indexes are ensured during the first DB access.
- No authentication is included in this version.
- A placeholder async ping utility is available in `app/utils/ping.py` for future reachability checks.
