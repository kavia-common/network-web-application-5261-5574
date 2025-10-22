import logging
from typing import Any, Dict

from flask_smorest import Blueprint
from flask.views import MethodView
from webargs import fields
from webargs.flaskparser import use_args
from marshmallow import Schema, INCLUDE, validates_schema, ValidationError

from pymongo.errors import DuplicateKeyError, PyMongoError

from app.services import db as db_service

logger = logging.getLogger(__name__)

blp = Blueprint(
    "Devices",
    "devices",
    url_prefix="/device",
    description="Device CRUD endpoints",
)


class DeviceSchema(Schema):
    class Meta:
        unknown = INCLUDE

    name = fields.String(required=True, description="Device name")
    ip_address = fields.String(required=True, description="IPv4 or IPv6 address")
    type = fields.String(required=True, description="Device type (router/switch/server)")
    location = fields.String(required=False, allow_none=True)
    status = fields.String(required=True, validate=lambda v: v in ["online", "offline"])
    last_ping_time = fields.String(required=False, description="ISO date-time")


class FindSchema(Schema):
    filter = fields.Dict(required=False, description="MongoDB filter query")
    sort = fields.List(
        fields.List(fields.Raw(), validate=lambda l: len(l) == 2),
        required=False,
        description="List of [field, direction]",
    )

    @validates_schema
    def validate_sort(self, data, **kwargs):
        sort = data.get("sort")
        if sort:
            for pair in sort:
                if not isinstance(pair, list) or len(pair) != 2:
                    raise ValidationError("Each sort entry must be [field, direction]")
                field, direction = pair
                if not isinstance(field, str) or direction not in [1, -1, "asc", "desc"]:
                    raise ValidationError("Invalid sort pair")
                if isinstance(direction, str):
                    if direction.lower() == "asc":
                        pair[1] = 1
                    elif direction.lower() == "desc":
                        pair[1] = -1
                    else:
                        raise ValidationError("Sort direction must be 1, -1, 'asc', or 'desc'")


class UpdateSchema(Schema):
    filter = fields.Dict(required=True, description="MongoDB filter query")
    update = fields.Dict(required=True, description="MongoDB update document")


class DeleteSchema(Schema):
    filter = fields.Dict(required=True, description="MongoDB filter query")


@blp.route("/insert")
class DeviceInsert(MethodView):
    @blp.doc(
        summary="Insert a new device record",
        description="Create a device document in MongoDB",
        operationId="insertDevice",
        responses={
            200: {"description": "Device inserted successfully"},
            400: {"description": "Invalid input"},
            500: {"description": "Database error"},
        },
        tags=["Devices"],
    )
    @use_args(DeviceSchema(), location="json")
    def post(self, device: Dict[str, Any]):
        try:
            inserted_id = db_service.insert_device(device)
            return {"inserted_id": inserted_id}, 200
        except DuplicateKeyError as e:
            msg = "Device with same name or ip_address already exists"
            logger.info("%s: %s", msg, e)
            return {"error": "DuplicateKeyError", "details": msg}, 400
        except PyMongoError as e:
            logger.exception("Insert failed: %s", e)
            return {"error": "DatabaseError", "details": str(e)}, 500


@blp.route("/find")
class DeviceFind(MethodView):
    @blp.doc(
        summary="Find device records with filtering and sorting",
        description="Return list of devices matching filter and sort",
        operationId="findDevices",
        responses={
            200: {"description": "List of matching device records"},
            400: {"description": "Invalid query"},
            500: {"description": "Database error"},
        },
        tags=["Devices"],
    )
    @use_args(FindSchema(), location="json")
    def post(self, args: Dict[str, Any]):
        try:
            filter_query = args.get("filter") or {}
            sort = args.get("sort")
            result = db_service.find_devices(filter_query=filter_query, sort=sort)
            return result, 200
        except PyMongoError as e:
            logger.exception("Find failed: %s", e)
            return {"error": "DatabaseError", "details": str(e)}, 500


@blp.route("/update")
class DeviceUpdate(MethodView):
    @blp.doc(
        summary="Update a device record",
        description="Update documents using filter and update doc",
        operationId="updateDevice",
        responses={
            200: {"description": "Device updated successfully"},
            400: {"description": "Invalid input"},
            500: {"description": "Database error"},
        },
        tags=["Devices"],
    )
    @use_args(UpdateSchema(), location="json")
    def post(self, args: Dict[str, Any]):
        try:
            res = db_service.update_device(args["filter"], args["update"])
            return res, 200
        except DuplicateKeyError as e:
            msg = "Duplicate key on update (name or ip_address)"
            logger.info("%s: %s", msg, e)
            return {"error": "DuplicateKeyError", "details": msg}, 400
        except PyMongoError as e:
            logger.exception("Update failed: %s", e)
            return {"error": "DatabaseError", "details": str(e)}, 500


@blp.route("/delete")
class DeviceDelete(MethodView):
    @blp.doc(
        summary="Delete a device record",
        description="Delete documents matching filter",
        operationId="deleteDevice",
        responses={
            200: {"description": "Device deleted successfully"},
            400: {"description": "Invalid input"},
            500: {"description": "Database error"},
        },
        tags=["Devices"],
    )
    @use_args(DeleteSchema(), location="json")
    def post(self, args: Dict[str, Any]):
        try:
            res = db_service.delete_device(args["filter"])
            return res, 200
        except PyMongoError as e:
            logger.exception("Delete failed: %s", e)
            return {"error": "DatabaseError", "details": str(e)}, 500
