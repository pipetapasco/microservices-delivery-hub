# servicio_pedidos/app/core/config.py
import logging
import os
from pathlib import Path

from dotenv import load_dotenv

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent.parent
ENV_PATH = BASE_DIR / ".env"

if ENV_PATH.exists():
    load_dotenv(dotenv_path=ENV_PATH)


class Settings:
    PROJECT_NAME: str = os.getenv("PROJECT_NAME", "Servicio de Pedidos")
    API_V1_STR: str = os.getenv("API_V1_STR", "/api/v1")
    PEDIDOS_SERVICE_PORT: int = int(os.getenv("PEDIDOS_SERVICE_PORT", 5003))

    SECRET_KEY: str = os.getenv("SECRET_KEY", "your-secret-key-here")  # Change in production!
    ALGORITHM: str = os.getenv("ALGORITHM", "HS256")

    POSTGRES_SERVER: str = os.getenv("POSTGRES_SERVER_PEDIDOS", "localhost")
    POSTGRES_PORT: str = os.getenv("POSTGRES_PORT_PEDIDOS", "5432")
    POSTGRES_USER: str = os.getenv("POSTGRES_USER_PEDIDOS", "")
    POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD_PEDIDOS", "")
    POSTGRES_DB: str = os.getenv("POSTGRES_DB_PEDIDOS", "")

    DATABASE_URL: str | None = None
    ASYNC_DATABASE_URL: str | None = None

    if POSTGRES_USER and POSTGRES_PASSWORD and POSTGRES_SERVER and POSTGRES_PORT and POSTGRES_DB:
        DATABASE_URL = f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_SERVER}:{POSTGRES_PORT}/{POSTGRES_DB}"
        ASYNC_DATABASE_URL = f"postgresql+asyncpg://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_SERVER}:{POSTGRES_PORT}/{POSTGRES_DB}"
    else:
        logger.warning("Missing PostgreSQL environment variables. DATABASE_URL not configured.")

    RABBITMQ_HOST: str = os.getenv("RABBITMQ_HOST", "localhost")
    RABBITMQ_PORT: int = int(os.getenv("RABBITMQ_PORT", 5672))
    RABBITMQ_USER: str = os.getenv("RABBITMQ_USER", "")
    RABBITMQ_PASSWORD: str = os.getenv("RABBITMQ_PASSWORD", "")
    RABBITMQ_PEDIDOS_EXCHANGE: str = os.getenv("RABBITMQ_PEDIDOS_EXCHANGE", "pedidos_exchange")
    RABBITMQ_PEDIDOS_QUEUE: str = os.getenv("RABBITMQ_PEDIDOS_QUEUE", "cola_pedidos_nuevos")
    RABBITMQ_PEDIDOS_ROUTING_KEY: str = os.getenv("RABBITMQ_PEDIDOS_ROUTING_KEY", "pedido.nuevo")
    RABBITMQ_DISPATCH_EXCHANGE: str = os.getenv(
        "RABBITMQ_DISPATCH_EXCHANGE", "dispatch_exchange_default"
    )
    RABBITMQ_DISPATCH_MOTOTAXI_ROUTING_KEY: str = os.getenv(
        "RABBITMQ_DISPATCH_MOTOTAXI_ROUTING_KEY", "pedido.requiere_mototaxi.default"
    )
    RABBITMQ_ORDER_UPDATES_QUEUE: str = os.getenv(
        "RABBITMQ_ORDER_UPDATES_QUEUE", "cola_actualizaciones_pedido_default"
    )
    RABBITMQ_ORDER_UPDATE_ROUTING_KEY: str = os.getenv(
        "RABBITMQ_ORDER_UPDATE_ROUTING_KEY", "pedido.conductor_acepto.default"
    )
    RABBITMQ_NOTIFY_CLIENT_ROUTING_KEY: str = os.getenv(
        "RABBITMQ_NOTIFY_CLIENT_ROUTING_KEY", "pedido.asignado_notificar_cliente.default"
    )


settings = Settings()

logger.info(
    f"Project: {settings.PROJECT_NAME}, API: {settings.API_V1_STR}, Port: {settings.PEDIDOS_SERVICE_PORT}"
)
if settings.DATABASE_URL:
    safe_url = (
        settings.DATABASE_URL.replace(settings.POSTGRES_PASSWORD, "********")
        if settings.POSTGRES_PASSWORD
        else settings.DATABASE_URL
    )
    logger.info(f"Database URL: {safe_url}")
else:
    logger.warning("DATABASE_URL: Not configured")
logger.info(
    f"RabbitMQ: {settings.RABBITMQ_HOST}:{settings.RABBITMQ_PORT}, Queue: {settings.RABBITMQ_PEDIDOS_QUEUE}"
)
