from app import app
from app.config import Config

"""
Entrypoint to run the Flask app.

Starts the application using host 0.0.0.0 to allow external connections
and listens on APP_PORT from environment (default 3001).
"""

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=Config.APP_PORT)
