"""
Punto de entrada principal del servicio de mototaxis.

FIX DE CONCURRENCIA:
- Se obtiene el Main Event Loop en el lifespan y se inyecta al consumidor
  usando `dispatch_event_consumer.set_main_loop(loop)`.
"""

import asyncio
import threading
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .api.endpoints import auth as auth_router, drivers as drivers_router
from .consumers import dispatch_event_consumer
from .core.config import settings
from .core.logger import get_logger
from .db.session import get_redis_client, init_db
from .websockets import location_ws as location_ws_router

logger = get_logger("main")
dispatch_consumer_thread = None


def run_dispatch_consumer_in_thread():
    logger.info("Iniciando hilo del consumidor de DESPACHO RabbitMQ...")
    try:
        dispatch_event_consumer.start_dispatch_consumer()
    except Exception as e:
        logger.exception(f"Error en el hilo del consumidor de despacho: {e}")
    finally:
        logger.info("Hilo del consumidor de despacho finalizado")


@asynccontextmanager
async def lifespan(app_instance: FastAPI):
    global dispatch_consumer_thread

    logger.info("Lifespan: Evento de inicio...")
    init_db()
    logger.info("Lifespan: DB PostgreSQL inicializada")

    redis_conn = get_redis_client()
    if redis_conn and redis_conn.ping():
        logger.info("Lifespan: Conexión a Redis OK")
    else:
        logger.warning("Lifespan: Conexión a Redis falló o cliente no inicializado")

    if settings.RABBITMQ_HOST:
        loop = asyncio.get_running_loop()
        dispatch_event_consumer.set_main_loop(loop)
        logger.info("Lifespan: Main Event Loop inyectado al consumidor")

        logger.info("Lifespan: Iniciando consumidor de eventos de despacho RabbitMQ...")
        dispatch_consumer_thread = threading.Thread(
            target=run_dispatch_consumer_in_thread, daemon=True, name="DispatchConsumerThread"
        )
        dispatch_consumer_thread.start()
        time.sleep(2)

        if dispatch_consumer_thread.is_alive():
            logger.info("Lifespan: Hilo del consumidor de DESPACHO RabbitMQ iniciado")
        else:
            logger.warning("Lifespan: Hilo consumidor de DESPACHO no pudo iniciar")
            dispatch_consumer_thread = None
    else:
        logger.warning(
            "Lifespan: Config RabbitMQ no encontrada, consumidor de DESPACHO no iniciado"
        )

    yield

    logger.info(f"Lifespan: Finalizando {settings.PROJECT_NAME}...")
    if dispatch_consumer_thread and dispatch_consumer_thread.is_alive():
        logger.info("Lifespan: Deteniendo consumidor de despacho RabbitMQ...")
        dispatch_event_consumer.stop_dispatch_consumer()
    logger.info("Lifespan: Proceso de finalización completado")


app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan,
)

app.include_router(
    auth_router.router, prefix=f"{settings.API_V1_STR}/auth", tags=["Authentication"]
)
app.include_router(drivers_router.router, prefix=settings.API_V1_STR)
app.include_router(location_ws_router.router)


@app.get("/", tags=["Root"])
async def read_root():
    return {"mensaje": f"Bienvenido a {settings.PROJECT_NAME}"}


@app.get("/health", tags=["Health"])
async def health_check():
    return {"status": "ok"}
