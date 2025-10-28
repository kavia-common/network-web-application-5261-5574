import logging
from typing import Any, Dict, List, Optional, Tuple

from flask_smorest import Blueprint
from flask.views import MethodView
from webargs import fields
from webargs.flaskparser import use_args
from marshmallow import Schema, INCLUDE, validates_schema, ValidationError, validates
from marshmallow.validate import OneOf

from pymongo.errors import DuplicateKeyError, PyMongoError

from app.services import db as db_service

logger = logging.getLogger(__name__)

blp = Blueprint(
    "Devices",
    "devices",
    url_prefix="/devices",
    description="RESTful Device CRUD endpoints",
)


class DeviceSchema(Schema):
    """
    Schema for a complete Device document. Used for POST (create) and PUT (full replace).
    """
    class Meta:
        unknown = INCLUDE

    name = fields.String(required=True, description="Device name")
    ip_address = fields.String(required=True, description="IPv4 or IPv6 address")
    type = fields.String(required=True, description="Device type (router/switch/server)")
    location = fields.String(required=False, allow_none=True)
    status = fields.String(required=False, validate=OneOf(["online", "offline"]))
    last_ping_time = fields.String(required=False, description="ISO date-time")

    @validates("name")
    def validate_name(self, value: str) -> None:
        if not value or not value.strip():
            raise ValidationError("name cannot be empty")


class PartialDeviceSchema(Schema):
    """
    Schema for partial updates (PATCH). All fields optional.
    """
    class Meta:
        unknown = INCLUDE

    name = fields.String(required=False)
    ip_address = fields.String(required=False)
    type = fields.String(required=False)
    location = fields.String(required=False, allow_none=True)
    status = fields.String(required=False, validate=OneOf(["online", "offline"]))
    last_ping_time = fields.String(required=False)


class ListQuerySchema(Schema):
    """
    Optional query params for GET /devices.
    """
    name = fields.String(required=False, description="Filter by name (exact match)")
    ip_address = fields.String(required=False, description="Filter by IP address (exact match)")
    type = fields.String(required=False, description="Filter by type (exact match)")
    status = fields.String(required=False, validate=OneOf(["online", "offline"]), description="Filter by status")
    location = fields.String(required=False, description="Filter by location (exact match)")
    sort = fields.String(required=False, description="Comma separated sort fields with optional :asc or :desc, e.g., name:asc,ip_address:desc")
    limit = fields.Integer(required=False, description="Limit number of results")
    skip = fields.Integer(required=False, description="Skip number of results")

    @validates_schema
    def validate_pagination(self, data, **kwargs):
        for key in ("limit", "skip"):
            if key in data and (not isinstance(data[key], int) or data[key] < 0):
                raise ValidationError(f"{key} must be a non-negative integer", field_name=key)


def _parse_sort(sort_param: Optional[str]) -> Optional[List[Tuple[str, int]]]:
    """
    Parse a comma-separated sort query param into pymongo sort format.
    Example: "name:asc,ip_address:desc" -> [("name", 1), ("ip_address", -1)]
    """
    if not sort_param:
        return None
    result: List[Tuple[str, int]] = []
    for part in sort_param.split(","):
        part = part.strip()
        if not part:
            continue
        if ":" in part:
            field, direction = part.split(":", 1)
            direction = direction.strip().lower()
            if direction not in ("asc", "desc"):
                raise ValidationError("Sort direction must be 'asc' or 'desc'")
            result.append((field.strip(), 1 if direction == "asc" else -1))
        else:
            result.append((part, 1))
    return result


def _make_filter_from_query(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build MongoDB filter from GET query params.
    Only exact match filters are applied for simplicity/clarity.
    """
    filter_query: Dict[str, Any] = {}
    for key in ("name", "ip_address", "type", "status", "location"):
        if args.get(key) is not None:
            filter_query[key] = args[key]
    return filter_query


@blp.route("")
class DevicesCollection(MethodView):
    @blp.doc(
        summary="Create a new device",
        description="Create a device document in MongoDB.",
        operationId="createDevice",
        responses={
            201: {"description": "Device created"},
            400: {"description": "Invalid input or duplicate key"},
            500: {"description": "Database error"},
        },
        tags=["Devices"],
    )
    @use_args(DeviceSchema(), location="json")
    def post(self, device: Dict[str, Any]):
        """
        Create a device. Returns 201 with inserted_id.
        """
        try:
            inserted_id = db_service.insert_device(device)
            return {"inserted_id": inserted_id}, 201
        except DuplicateKeyError as e:
            msg = "Device with same name or ip_address already exists"
            logger.info("%s: %s", msg, e)
            return {"error": "DuplicateKeyError", "details": msg}, 400
        except PyMongoError as e:
            logger.exception("Insert failed: %s", e)
            return {"error": "DatabaseError", "details": str(e)}, 500

    @blp.doc(
        summary="List devices",
        description="List devices. Optional query parameters for filtering and sorting.",
        operationId="listDevices",
        responses={
            200: {"description": "List of device records"},
            400: {"description": "Invalid query"},
            500: {"description": "Database error"},
        },
        tags=["Devices"],
    )
    @use_args(ListQuerySchema(), location="query")
    def get(self, args: Dict[str, Any]):
        """
        List devices with optional filter/sort/limit/skip.
        """
        try:
            filter_query = _make_filter_from_query(args)
            sort = _parse_sort(args.get("sort"))
            devices = db_service.find_devices(filter_query=filter_query, sort=sort, limit=args.get("limit"), skip=args.get("skip"))
            return devices, 200
        except ValidationError as e:
            return {"error": "ValidationError", "details": e.messages}, 400
        except PyMongoError as e:
            logger.exception("Find failed: %s", e)
            return {"error": "DatabaseError", "details": str(e)}, 500


@blp.route("/<string:device_id>")
class DeviceItem(MethodView):
    @blp.doc(
        summary="Get device by id",
        description="Retrieve a single device by its ObjectId.",
        operationId="getDeviceById",
        responses={
            200: {"description": "Device found"},
            400: {"description": "Invalid ObjectId"},
            404: {"description": "Device not found"},
            500: {"description": "Database error"},
        },
        tags=["Devices"],
    )
    def get(self, device_id: str):
        try:
            device = db_service.get_by_id(device_id)
            if not device:
                return {"error": "NotFound", "details": "Device not found"}, 404
            return device, 200
        except ValueError as e:
            return {"error": "InvalidObjectId", "details": str(e)}, 400
        except PyMongoError as e:
            logger.exception("Get by id failed: %s", e)
            return {"error": "DatabaseError", "details": str(e)}, 500

    @blp.doc(
        summary="Replace a device (idempotent)",
        description="Fully replace a device document. All required fields must be present. Idempotent semantics.",
        operationId="replaceDevice",
        responses={
            200: {"description": "Device replaced"},
            201: {"description": "Device created (if upsert is used)"},
            400: {"description": "Invalid ObjectId or payload"},
            404: {"description": "Device not found"},
            409: {"description": "Duplicate key"},
            500: {"description": "Database error"},
        },
        tags=["Devices"],
    )
    @use_args(DeviceSchema(), location="json")
    def put(self, payload: Dict[str, Any], device_id: str):
        """
        PUT replaces the device. If the device does not exist, respond 404 (no implicit upsert).
        """
        try:
            # Ensure exists first to keep semantics of 404 if not present.
            existing = db_service.get_by_id(device_id)
            if not existing:
                return {"error": "NotFound", "details": "Device not found"}, 404
            updated = db_service.replace_one_by_id(device_id, payload)
            return updated, 200
        except ValueError as e:
            return {"error": "InvalidObjectId", "details": str(e)}, 400
        except DuplicateKeyError:
            return {"error": "DuplicateKeyError", "details": "Duplicate name or ip_address"}, 409
        except PyMongoError as e:
            logger.exception("Replace failed: %s", e)
            return {"error": "DatabaseError", "details": str(e)}, 500

    @blp.doc(
        summary="Partially update a device",
        description="Apply partial updates to a device document by id. Validates fields.",
        operationId="patchDevice",
        responses={
            200: {"description": "Device updated"},
            400: {"description": "Invalid ObjectId or payload"},
            404: {"description": "Device not found"},
            409: {"description": "Duplicate key"},
            500: {"description": "Database error"},
        },
        tags=["Devices"],
    )
    @use_args(PartialDeviceSchema(), location="json")
    def patch(self, payload: Dict[str, Any], device_id: str):
        if not payload:
            return {"error": "ValidationError", "details": "No fields provided for update"}, 400
        try:
            updated = db_service.update_one_by_id(device_id, payload)
            if not updated:
                return {"error": "NotFound", "details": "Device not found"}, 404
            return updated, 200
        except ValueError as e:
            return {"error": "InvalidObjectId", "details": str(e)}, 400
        except DuplicateKeyError:
            return {"error": "DuplicateKeyError", "details": "Duplicate name or ip_address"}, 409
        except PyMongoError as e:
            logger.exception("Patch failed: %s", e)
            return {"error": "DatabaseError", "details": str(e)}, 500

    @blp.doc(
        summary="Delete a device",
        description="Delete a device by id.",
        operationId="deleteDeviceById",
        responses={
            204: {"description": "Device deleted"},
            200: {"description": "Device deleted (with confirmation message)"},
            400: {"description": "Invalid ObjectId"},
            404: {"description": "Device not found"},
            500: {"description": "Database error"},
        },
        tags=["Devices"],
    )
    def delete(self, device_id: str):
        try:
            deleted = db_service.delete_one_by_id(device_id)
            if not deleted:
                return {"error": "NotFound", "details": "Device not found"}, 404
            # Return 204 with no content to be strictly RESTful; some clients prefer message
            return "", 204
        except ValueError as e:
            return {"error": "InvalidObjectId", "details": str(e)}, 400
        except PyMongoError as e:
            logger.exception("Delete failed: %s", e)
            return {"error": "DatabaseError", "details": str(e)}, 500
