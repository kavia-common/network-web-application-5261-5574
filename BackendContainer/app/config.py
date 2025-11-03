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
