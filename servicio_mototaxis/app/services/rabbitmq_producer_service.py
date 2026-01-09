"""
Productor de eventos RabbitMQ para el servicio de mototaxis.

FIX DE CONCURRENCIA:
- La función `publicar_evento_actualizacion_pedido` es async pero usa pika (bloqueante).
- Se envuelve la lógica de publicación en `asyncio.to_thread()` para no congelar el Event Loop.
"""

import asyncio
import contextlib
import json
import threading

import pika

from ..core.config import settings
from ..core.logger import get_logger

logger = get_logger("rabbitmq_producer")

_connection_producer = None
_channel_producer = None
_producer_lock = threading.Lock()


def _get_rabbitmq_producer_channel():
    """Obtiene o crea el canal de RabbitMQ de forma thread-safe."""
    global _connection_producer, _channel_producer

    with _producer_lock:
        if _channel_producer is None or _channel_producer.is_closed:
            try:
                credentials = pika.PlainCredentials(
                    settings.RABBITMQ_USER, settings.RABBITMQ_PASSWORD
                )
                parameters = pika.ConnectionParameters(
                    host=settings.RABBITMQ_HOST,
                    port=settings.RABBITMQ_PORT,
                    credentials=credentials,
                    heartbeat=60,
                    blocked_connection_timeout=300,
                )
                _connection_producer = pika.BlockingConnection(parameters)
                _channel_producer = _connection_producer.channel()

                _channel_producer.exchange_declare(
                    exchange=settings.RABBITMQ_DISPATCH_EXCHANGE,
                    exchange_type="direct",
                    durable=True,
                )
                logger.info(
                    f"Conectado a RabbitMQ. Exchange '{settings.RABBITMQ_DISPATCH_EXCHANGE}' asegurado"
                )
            except Exception as e:
                logger.error(f"Error conectando a RabbitMQ: {e}", exc_info=True)
                _channel_producer = None
                _connection_producer = None
                raise

        return _channel_producer


def _publicar_sync(routing_key: str, mensaje_json: str) -> bool:
    """
    Función síncrona interna que realiza la publicación bloqueante.
    Esta función será ejecutada en un hilo separado via asyncio.to_thread().
    """
    try:
        channel = _get_rabbitmq_producer_channel()
        if not channel:
            logger.error("Canal no disponible. Evento no publicado")
            return False

        channel.basic_publish(
            exchange=settings.RABBITMQ_DISPATCH_EXCHANGE,
            routing_key=routing_key,
            body=mensaje_json,
            properties=pika.BasicProperties(delivery_mode=pika.spec.PERSISTENT_DELIVERY_MODE),
        )
        logger.info(
            f"Evento publicado. Exchange: '{settings.RABBITMQ_DISPATCH_EXCHANGE}', RK: '{routing_key}'"
        )
        return True

    except Exception as e:
        logger.error(f"Error publicando evento: {e}", exc_info=True)
        global _channel_producer, _connection_producer
        with _producer_lock:
            _channel_producer = None
            if _connection_producer and not _connection_producer.is_closed:
                with contextlib.suppress(Exception):
                    _connection_producer.close()
            _connection_producer = None
        return False


async def publicar_evento_actualizacion_pedido(routing_key: str, datos_evento: dict) -> bool:
    """
    Publica un evento de actualización de estado de pedido.

    FIX CONCURRENCIA:
    - Ejecuta la publicación bloqueante en un hilo separado usando asyncio.to_thread()
    - Esto evita congelar el Event Loop de FastAPI mientras espera a RabbitMQ
    """
    mensaje_json = json.dumps(datos_evento, default=str)

    return await asyncio.to_thread(_publicar_sync, routing_key, mensaje_json)


def cerrar_conexion_productor_mototaxis_rabbitmq():
    """Cierra la conexión del productor RabbitMQ."""
    global _connection_producer, _channel_producer

    with _producer_lock:
        if _channel_producer and not _channel_producer.is_closed:
            try:
                _channel_producer.close()
            except Exception as e:
                logger.error(f"Error cerrando canal: {e}")

        if _connection_producer and not _connection_producer.is_closed:
            try:
                _connection_producer.close()
            except Exception as e:
                logger.error(f"Error cerrando conexión: {e}")

        _channel_producer = None
        _connection_producer = None
        logger.info("Conexión de productor RabbitMQ cerrada")
