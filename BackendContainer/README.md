# Network Device Management Backend (Flask)

This Flask backend provides RESTful CRUD endpoints for managing network devices and integrates with MongoDB using `pymongo`. It includes schema validation at the MongoDB level, unique indexes, environment-based configuration, and basic logging.

## Features

- CRUD endpoints:
  - POST /device/insert
  - POST /device/find
  - POST /device/update
  - POST /device/delete
- Health check: GET /
- MongoDB integration via `pymongo`
- Collection JSON schema validator and unique indexes on `name` and `ip_address`
- Environment variables with sensible defaults
- Logging with configurable level
- OpenAPI documentation via `flask-smorest` at `/docs`
- Optional async ping utility scaffold (`app/utils/ping.py`)

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

## API Overview

- POST `/device/insert`
  - Body: `{ "name": "...", "ip_address": "...", "type": "...", "location": "...", "status": "online|offline", "last_ping_time": "ISO-8601" }`
  - Response: `{ "inserted_id": "<ObjectId as string>" }`

- POST `/device/find`
  - Body: `{ "filter": {...}, "sort": [["name", 1]] }` (both optional)
  - Response: `[ Device, ... ]`

- POST `/device/update`
  - Body: `{ "filter": {...}, "update": { "$set": { ... } } }`
  - Response: `{ "matched_count": N, "modified_count": M }`

- POST `/device/delete`
  - Body: `{ "filter": {...} }`
  - Response: `{ "deleted_count": N }`

All endpoints return appropriate error messages for validation errors, duplicate keys, and database errors.

## Notes

- The collection validator and indexes are ensured during the first DB access.
- No authentication is included in this version.
- A placeholder async ping utility is available in `app/utils/ping.py` for future reachability checks.
