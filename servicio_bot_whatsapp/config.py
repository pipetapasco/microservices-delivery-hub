"""Configuration module with strict validation."""

import contextlib
import os
import sys

from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_PATH = os.path.join(BASE_DIR, ".env")

if os.path.exists(ENV_PATH):
    load_dotenv(dotenv_path=ENV_PATH)


def _get_required_env(key: str) -> str:
    """Get required environment variable or exit."""
    value = os.getenv(key)
    if not value:
        print(f"FATAL: Required environment variable {key} is not set", file=sys.stderr)
        sys.exit(1)
    return value


def _get_int_env(key: str, default: int) -> int:
    """Get integer environment variable with default."""
    value = os.getenv(key)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_WHATSAPP_NUMBER = os.getenv("TWILIO_WHATSAPP_NUMBER")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

REDIS_URL = os.getenv("REDIS_URL")

RABBITMQ_HOST = os.getenv("RABBITMQ_HOST")
RABBITMQ_PORT = _get_int_env("RABBITMQ_PORT", 5672)
RABBITMQ_USER = os.getenv("RABBITMQ_USER", "guest")
RABBITMQ_PASSWORD = os.getenv("RABBITMQ_PASSWORD", "guest")

RABBITMQ_HEARTBEAT = _get_int_env("RABBITMQ_HEARTBEAT", 600)
RABBITMQ_BLOCKED_CONNECTION_TIMEOUT = _get_int_env("RABBITMQ_BLOCKED_CONNECTION_TIMEOUT", 300)

RABBITMQ_PEDIDOS_EXCHANGE = os.getenv("RABBITMQ_PEDIDOS_EXCHANGE", "pedidos_exchange")
RABBITMQ_PEDIDOS_QUEUE = os.getenv("RABBITMQ_PEDIDOS_QUEUE", "cola_pedidos_nuevos")
RABBITMQ_PEDIDOS_ROUTING_KEY = os.getenv("RABBITMQ_PEDIDOS_ROUTING_KEY", "pedido.nuevo")

RABBITMQ_DISPATCH_EXCHANGE = os.getenv("RABBITMQ_DISPATCH_EXCHANGE", "dispatch_exchange")
RABBITMQ_CLIENT_NOTIFICATION_QUEUE = os.getenv(
    "RABBITMQ_CLIENT_NOTIFICATION_QUEUE", "cola_notificaciones_cliente_bot"
)
RABBITMQ_NOTIFY_CLIENT_ROUTING_KEY = os.getenv(
    "RABBITMQ_NOTIFY_CLIENT_ROUTING_KEY", "pedido.asignado_notificar_cliente"
)

INCOMING_MESSAGES_EXCHANGE = os.getenv("INCOMING_MESSAGES_EXCHANGE", "incoming_messages_exchange")
INCOMING_MESSAGES_QUEUE = os.getenv("INCOMING_MESSAGES_QUEUE", "incoming_messages")
INCOMING_MESSAGES_ROUTING_KEY = os.getenv("INCOMING_MESSAGES_ROUTING_KEY", "message.incoming")

AUDIO_STORAGE_PATH = os.path.join(BASE_DIR, "temp_audio")
WHISPER_MODEL_SIZE = os.getenv("WHISPER_MODEL_SIZE", "small")

MAX_AUDIO_SIZE_MB = _get_int_env("MAX_AUDIO_SIZE_MB", 10)
MAX_REQUEST_SIZE_BYTES = _get_int_env("MAX_REQUEST_SIZE_BYTES", 10 * 1024 * 1024)

RATE_LIMIT_REQUESTS = _get_int_env("RATE_LIMIT_REQUESTS", 30)
RATE_LIMIT_WINDOW_SECONDS = _get_int_env("RATE_LIMIT_WINDOW_SECONDS", 60)

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
ENVIRONMENT = os.getenv("ENVIRONMENT", "production")

if not os.path.exists(AUDIO_STORAGE_PATH):
    with contextlib.suppress(OSError):
        os.makedirs(AUDIO_STORAGE_PATH)


def validate_webhook_config() -> None:
    """Validate required config for webhook. Called on app startup."""
    from logger import get_logger

    logger = get_logger(__name__)

    errors = []

    if not AUTH_TOKEN:
        errors.append("TWILIO_AUTH_TOKEN is required for webhook security")

    if not REDIS_URL:
        errors.append("REDIS_URL is required for session and rate limiting")

    if not RABBITMQ_HOST:
        errors.append("RABBITMQ_HOST is required for message queuing")

    if errors:
        for error in errors:
            logger.error(f"Configuration error: {error}")
        raise SystemExit("Missing required configuration. See errors above.")

    logger.info("Webhook configuration validated")


def validate_worker_config() -> None:
    """Validate required config for worker. Called on worker startup."""
    from logger import get_logger

    logger = get_logger(__name__)

    errors = []

    if not REDIS_URL:
        errors.append("REDIS_URL is required for session management")

    if not RABBITMQ_HOST:
        errors.append("RABBITMQ_HOST is required for message consumption")

    if not GEMINI_API_KEY:
        errors.append("GEMINI_API_KEY is required for message analysis")

    if not ACCOUNT_SID or not AUTH_TOKEN:
        errors.append("Twilio credentials are required for sending messages")

    if errors:
        for error in errors:
            logger.error(f"Configuration error: {error}")
        raise SystemExit("Missing required configuration. See errors above.")

    logger.info("Worker configuration validated")
    logger.info(
        f"RabbitMQ heartbeat: {RABBITMQ_HEARTBEAT}s, blocked timeout: {RABBITMQ_BLOCKED_CONNECTION_TIMEOUT}s"
    )
