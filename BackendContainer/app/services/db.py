import logging
from typing import Any, Dict, List, Optional, Tuple

from pymongo import MongoClient, ASCENDING
from pymongo.collection import Collection
from pymongo.errors import DuplicateKeyError, PyMongoError
from bson import ObjectId
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
        _client = MongoClient("ac-d4x385z-shard-00-00.htz84wq.mongodb.net:27017")
        #_client = MongoClient(Config.MONGO_URI, uuidRepresentation="standard")
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


def _normalize_dates(doc: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert last_ping_time from ISO string to datetime for DB write operations.
    """
    out = dict(doc)
    if "last_ping_time" in out and isinstance(out["last_ping_time"], str):
        try:
            out["last_ping_time"] = datetime.fromisoformat(out["last_ping_time"])
        except ValueError:
            # Remove invalid date so schema can still pass if optional
            out.pop("last_ping_time", None)
    return out


def _serialize_device(doc: Dict[str, Any]) -> Dict[str, Any]:
    """
    Serialize Mongo document to JSON-friendly dict.
    """
    data = dict(doc)
    if "_id" in data and isinstance(data["_id"], ObjectId):
        data["_id"] = str(data["_id"])
    if "last_ping_time" in data and isinstance(data["last_ping_time"], datetime):
        data["last_ping_time"] = data["last_ping_time"].isoformat()
    return data


def _parse_object_id(id_str: str) -> ObjectId:
    """
    Safely parse an ObjectId from string or raise ValueError.
    """
    try:
        return ObjectId(id_str)
    except Exception:
        raise ValueError("Invalid ObjectId")


# PUBLIC_INTERFACE
def insert_device(device: Dict[str, Any]) -> str:
    """Insert a new device document. Returns inserted_id as str."""
    col = get_collection()
    doc = _normalize_dates(device)
    try:
        result = col.insert_one(doc)
        return str(result.inserted_id)
    except DuplicateKeyError:
        logger.info("Duplicate key error on insert")
        raise
    except PyMongoError:
        logger.exception("Database error during insert")
        raise


# PUBLIC_INTERFACE
def find_devices(
    filter_query: Optional[Dict[str, Any]] = None,
    sort: Optional[List[Tuple[str, int]]] = None,
    limit: Optional[int] = None,
    skip: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Find devices matching a filter and optional sort/pagination."""
    col = get_collection()
    filter_query = filter_query or {}
    cursor = col.find(filter_query)
    if sort:
        cursor = cursor.sort(sort)
    if skip is not None:
        cursor = cursor.skip(int(skip))
    if limit is not None:
        cursor = cursor.limit(int(limit))
    items: List[Dict[str, Any]] = []
    for item in cursor:
        items.append(_serialize_device(item))
    return items


# PUBLIC_INTERFACE
def update_device(
    filter_query: Dict[str, Any],
    update_doc: Dict[str, Any],
) -> Dict[str, int]:
    """Update multiple devices using filter and update document. Returns matched and modified counts."""
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


# PUBLIC_INTERFACE
def get_by_id(id_str: str) -> Optional[Dict[str, Any]]:
    """Get a single device by ObjectId string. Returns serialized device or None."""
    col = get_collection()
    oid = _parse_object_id(id_str)
    doc = col.find_one({"_id": oid})
    return _serialize_device(doc) if doc else None


# PUBLIC_INTERFACE
def replace_one_by_id(id_str: str, new_doc: Dict[str, Any]) -> Dict[str, Any]:
    """Replace a device document by id. Returns the updated document."""
    col = get_collection()
    oid = _parse_object_id(id_str)
    to_set = _normalize_dates(new_doc)
    # Ensure _id is preserved and not overwritten by client
    to_set.pop("_id", None)
    try:
        res = col.replace_one({"_id": oid}, to_set, upsert=False)
        if res.matched_count == 0:
            # caller decides 404
            return {}
        # Return the updated document
        doc = col.find_one({"_id": oid})
        return _serialize_device(doc) if doc else {}
    except DuplicateKeyError:
        logger.info("Duplicate key error on replace")
        raise
    except PyMongoError:
        logger.exception("Database error during replace")
        raise


# PUBLIC_INTERFACE
def update_one_by_id(id_str: str, partial: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Apply a partial update to a device by id. Returns updated document or None if not found."""
    col = get_collection()
    oid = _parse_object_id(id_str)
    update_fields = _normalize_dates(partial)
    update_fields.pop("_id", None)
    if not update_fields:
        return None
    try:
        res = col.update_one({"_id": oid}, {"$set": update_fields})
        if res.matched_count == 0:
            return None
        doc = col.find_one({"_id": oid})
        return _serialize_device(doc) if doc else None
    except DuplicateKeyError:
        logger.info("Duplicate key error on partial update")
        raise
    except PyMongoError:
        logger.exception("Database error during partial update")
        raise


# PUBLIC_INTERFACE
def delete_one_by_id(id_str: str) -> bool:
    """Delete a device by id. Returns True if deleted, False if not found."""
    col = get_collection()
    oid = _parse_object_id(id_str)
    try:
        res = col.delete_one({"_id": oid})
        return res.deleted_count == 1
    except PyMongoError:
        logger.exception("Database error during delete by id")
        raise
