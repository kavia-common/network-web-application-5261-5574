import os
import logging
from dotenv import load_dotenv

# Load environment variables from .env if present
load_dotenv()


class Config:
    """Application configuration loaded from environment variables with sensible defaults."""
    APP_PORT: int = int(os.getenv("APP_PORT", "3001"))
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").upper()

    MONGO_URI: str = os.getenv("MONGO_URI", "mongodb+srv://db_user:vettel%402012@cluster0.htz84wq.mongodb.net/network?retryWrites=true&w=majority
")
    MONGO_DB_NAME: str = os.getenv("MONGO_DB_NAME", "network_devices")
    MONGO_COLLECTION: str = os.getenv("MONGO_COLLECTION", "devices")


def setup_logging(level: str) -> None:
    """Configure root logging according to the provided level."""
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(
        level=numeric_level,
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )
