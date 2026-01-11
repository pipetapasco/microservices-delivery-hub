"""Flask application entry point - Web API only."""

import atexit
import os

from flask import Flask

import config
from api.webhook import webhook_bp
from logger import get_logger
from services.rabbitmq_service import close_all_connections
from services.redis_client import close_redis_connection

logger = get_logger(__name__)


def create_app() -> Flask:
    """Application factory."""
    config.validate_webhook_config()

    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = config.MAX_REQUEST_SIZE_BYTES

    app.register_blueprint(webhook_bp)

    atexit.register(close_redis_connection)
    atexit.register(close_all_connections)

    logger.info("Flask application created")
    return app


app = create_app()


if __name__ == "__main__":
    FLASK_PORT = int(os.getenv("FLASK_RUN_PORT", 5000))

    try:
        app.run(debug=False, port=FLASK_PORT, host="0.0.0.0", use_reloader=False)
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
