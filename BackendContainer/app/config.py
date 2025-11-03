import os
import logging
from urllib.parse import urlparse
from dotenv import load_dotenv

# Load environment variables from .env if present
load_dotenv()


class Config:
    """Application configuration loaded from environment variables with sensible defaults."""
    # Use port 3001 by default for preview environments
    APP_PORT: int = int(os.getenv("APP_PORT", "3001"))
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").upper()

    # Safe default for local development with no credentials and no trailing newline
    MONGO_URI: str = os.getenv("MONGO_URI", "mongodb://localhost:27017")
    MONGO_DB_NAME: str = os.getenv("MONGO_DB_NAME", "network_devices")
    MONGO_COLLECTION: str = os.getenv("MONGO_COLLECTION", "devices")

    # CORS configuration
    # Comma-separated list of allowed origins. If not provided, default to the known frontend URL.
    # For development, you may set to "*" (wildcard) to allow all origins.
    FRONTEND_DEFAULT_ORIGIN: str = "https://network-web-application-1.kavia.app"
    ALLOWED_ORIGINS_RAW: str = os.getenv("ALLOWED_ORIGINS", FRONTEND_DEFAULT_ORIGIN)
    # Normalize to list; accept comma-separated items and strip spaces
    ALLOWED_ORIGINS: list[str] = [o.strip() for o in ALLOWED_ORIGINS_RAW.split(",") if o.strip()]

    # Allowed HTTP methods and headers for CORS
    CORS_ALLOW_CREDENTIALS: bool = os.getenv("CORS_ALLOW_CREDENTIALS", "true").lower() == "true"
    CORS_METHODS: list[str] = [m.strip() for m in os.getenv(
        "CORS_METHODS",
        "GET,POST,PUT,PATCH,DELETE,OPTIONS"
    ).split(",") if m.strip()]
    CORS_ALLOW_HEADERS: list[str] = [h.strip() for h in os.getenv(
        "CORS_ALLOW_HEADERS",
        "Content-Type,Authorization,X-Requested-With"
    ).split(",") if h.strip()]


def setup_logging(level: str) -> None:
    """Configure root logging according to the provided level."""
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(
        level=numeric_level,
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )
    # Optional non-secret diagnostics: log only the Mongo host
    try:
        parsed = urlparse(Config.MONGO_URI)
        host_display = parsed.hostname or "unknown"
        logging.getLogger(__name__).info("Mongo host: %s", host_display)
    except Exception:
        # Fail silently to avoid breaking startup due to logging
        pass
