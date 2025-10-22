import logging
from typing import Any, Dict, List, Optional, Tuple

from pymongo import MongoClient, ASCENDING
from pymongo.collection import Collection
from pymongo.errors import DuplicateKeyError, PyMongoError
from datetime import datetime

from app.config import Config

logger = logging.getLogger(__name__)

_client: Optional[MongoClient] = None
_collection: Optional[Collection] = None


def _get_client() -> MongoClient:
    """Get a singleton MongoClient instance."""
    global _client
    if _client is None:
        logger.info("Initializing MongoDB client")
        _client = MongoClient(Config.MONGO_URI, uuidRepresentation="standard")
    return _client


def get_collection() -> Collection:
    """Get the MongoDB collection, ensuring validator and indexes exist."""
    global _collection
    if _collection is not None:
        return _collection

    client = _get_client()
    db = client[Config.MONGO_DB_NAME]

    # Ensure collection exists with validator
    coll_name = Config.MONGO_COLLECTION
    validator = {
        "$jsonSchema": {
            "bsonType": "object",
            "required": ["name", "ip_address", "type", "status"],
            "properties": {
                "name": {"bsonType": "string", "description": "Device name, unique"},
                "ip_address": {
                    "bsonType": "string",
                    "pattern": r"^(?:[0-9]{1,3}\.){3}[0-9]{1,3}$|^([a-fA-F0-9:]+)$",
                    "description": "IPv4 or IPv6 address, unique",
                },
                "type": {
                    "bsonType": "string",
                    "description": "Device type (router, switch, server, etc.)",
                },
                "location": {"bsonType": "string"},
                "status": {
                    "enum": ["online", "offline"],
                    "description": "Device status",
                },
                "last_ping_time": {"bsonType": "date"},
            },
        }
    }

    try:
        if coll_name not in db.list_collection_names():
            logger.info("Creating collection '%s' with validator", coll_name)
            db.create_collection(
                coll_name,
                validator=validator,
                validationLevel="strict",
                validationAction="error",
            )
        else:
            # Try to update validator if collection exists (not fatal if fails due to permissions)
            try:
                logger.info("Updating validator on collection '%s'", coll_name)
                db.command(
                    "collMod",
                    coll_name,
                    validator=validator,
                    validationLevel="strict",
                    validationAction="error",
                )
            except Exception as e:
                logger.warning("Unable to update validator: %s", e)
        collection = db[coll_name]

        # Ensure unique indexes
        logger.info("Ensuring unique indexes on 'ip_address' and 'name'")
        collection.create_index([("ip_address", ASCENDING)], unique=True, name="uniq_ip")
        collection.create_index([("name", ASCENDING)], unique=True, name="uniq_name")

        _collection = collection
        return collection
    except PyMongoError as e:
        logger.exception("Failed to initialize MongoDB collection: %s", e)
        raise


# PUBLIC_INTERFACE
def insert_device(device: Dict[str, Any]) -> str:
    """Insert a new device document. Returns inserted_id as str."""
    col = get_collection()
    # Normalize fields
    doc = dict(device)
    # Convert last_ping_time if provided as ISO string
    if "last_ping_time" in doc and isinstance(doc["last_ping_time"], str):
        try:
            doc["last_ping_time"] = datetime.fromisoformat(doc["last_ping_time"])
        except ValueError:
            # Let Mongo validator handle wrong types or remove invalid date
            doc.pop("last_ping_time", None)

    try:
        result = col.insert_one(doc)
        return str(result.inserted_id)
    except DuplicateKeyError as e:
        logger.info("Duplicate key error on insert: %s", e)
        # Determine which field caused duplicate if possible
        raise
    except PyMongoError:
        logger.exception("Database error during insert")
        raise


# PUBLIC_INTERFACE
def find_devices(
    filter_query: Optional[Dict[str, Any]] = None,
    sort: Optional[List[Tuple[str, int]]] = None,
) -> List[Dict[str, Any]]:
    """Find devices matching a filter and optional sort."""
    col = get_collection()
    filter_query = filter_query or {}
    cursor = col.find(filter_query)
    if sort:
        cursor = cursor.sort(sort)
    items: List[Dict[str, Any]] = []
    for item in cursor:
        item["_id"] = str(item["_id"])
        # Convert datetime to isoformat
        if "last_ping_time" in item and isinstance(item["last_ping_time"], datetime):
            item["last_ping_time"] = item["last_ping_time"].isoformat()
        items.append(item)
    return items


# PUBLIC_INTERFACE
def update_device(
    filter_query: Dict[str, Any],
    update_doc: Dict[str, Any],
) -> Dict[str, int]:
    """Update a device using filter and update document. Returns matched and modified counts."""
    col = get_collection()
    try:
        res = col.update_many(filter_query, update_doc)
        return {"matched_count": res.matched_count, "modified_count": res.modified_count}
    except DuplicateKeyError:
        logger.info("Duplicate key error on update")
        raise
    except PyMongoError:
        logger.exception("Database error during update")
        raise


# PUBLIC_INTERFACE
def delete_device(filter_query: Dict[str, Any]) -> Dict[str, int]:
    """Delete devices matching the filter. Returns deleted_count."""
    col = get_collection()
    try:
        res = col.delete_many(filter_query)
        return {"deleted_count": res.deleted_count}
    except PyMongoError:
        logger.exception("Database error during delete")
        raise
