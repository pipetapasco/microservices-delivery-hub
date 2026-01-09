# servicio_pedidos/app/main.py
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .api.endpoints import orders as orders_router
from .consumers import async_order_consumer, async_update_consumer
from .core.config import settings
from .core.logging_config import get_logger
from .db.session import init_db_pedidos
from .services.rabbitmq_connection import rabbitmq_connection

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app_instance: FastAPI):
    """
    Async lifespan context manager for FastAPI.
    Handles startup and shutdown of async resources.
    """
    logger.info(f"Lifespan: Starting {settings.PROJECT_NAME}...")

    # Initialize database
    await init_db_pedidos()
    logger.info("Lifespan: Database initialized.")

    # Start RabbitMQ consumers as async tasks (no threading!)
    if settings.RABBITMQ_HOST and settings.RABBITMQ_USER:
        try:
            # Connect to RabbitMQ
            await rabbitmq_connection.connect()

            # Start consumers as async tasks
            logger.info("Lifespan: Starting async order consumer...")
            async_order_consumer.create_order_consumer_task()

            logger.info("Lifespan: Starting async update consumer...")
            async_update_consumer.create_update_consumer_task()

            logger.info("Lifespan: All consumers started successfully.")
        except Exception as e:
            logger.exception(f"Lifespan: Failed to start RabbitMQ consumers: {e}")
    else:
        logger.warning("Lifespan: RabbitMQ config not found, consumers not started.")

    yield

    # Shutdown
    logger.info(f"Lifespan: Shutting down {settings.PROJECT_NAME}...")

    # Stop consumers gracefully
    await async_order_consumer.stop_order_consumer()
    await async_update_consumer.stop_update_consumer()

    # Close RabbitMQ connection
    await rabbitmq_connection.close()

    logger.info("Lifespan: Shutdown complete.")


app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan,
)

app.include_router(orders_router.router, prefix=settings.API_V1_STR + "/orders", tags=["Pedidos"])


@app.get("/", tags=["Root"])
async def read_root():
    return {"mensaje": f"Bienvenido a {settings.PROJECT_NAME}"}


@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": settings.PROJECT_NAME,
        "rabbitmq_connected": rabbitmq_connection.is_connected,
    }
