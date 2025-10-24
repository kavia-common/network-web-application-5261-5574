from flask import Flask
from flask_cors import CORS
from flask_smorest import Api
import logging

from app.config import Config, setup_logging
from .routes.health import blp as health_blp
from .routes.devices import blp as devices_blp

# Initialize logging from config
setup_logging(Config.LOG_LEVEL)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.url_map.strict_slashes = False

# CORS: allow all origins (can be restricted via env if needed)
CORS(app)

# OpenAPI/Swagger config
app.config["API_TITLE"] = "Network Device Management API"
app.config["API_VERSION"] = "v1"
app.config["OPENAPI_VERSION"] = "3.0.3"
app.config["OPENAPI_URL_PREFIX"] = "/docs"
app.config["OPENAPI_SWAGGER_UI_PATH"] = ""
app.config["OPENAPI_SWAGGER_UI_URL"] = "https://cdn.jsdelivr.net/npm/swagger-ui-dist/"
app.config["CORS_HEADERS"] = "Content-Type"

api = Api(app, spec_kwargs={"title": app.config["API_TITLE"], "version": app.config["API_VERSION"]})
api.register_blueprint(health_blp)
api.register_blueprint(devices_blp)

logger.info("Flask app initialized. OpenAPI docs available at /docs")
