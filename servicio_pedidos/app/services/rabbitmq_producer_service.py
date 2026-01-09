# servicio_pedidos/app/services/rabbitmq_producer_service.py
"""
Async RabbitMQ producer using aio-pika.
"""
import json

from aio_pika import DeliveryMode, Message

from ..core.config import settings
from ..core.logging_config import get_logger
from .rabbitmq_connection import rabbitmq_connection

logger = get_logger(__name__)


async def publicar_evento_pedido_para_despacho(
    tipo_despacho_key: str, datos_pedido_evento: dict
) -> bool:
    """
    Publishes an order event to RabbitMQ for dispatch.

    Args:
        tipo_despacho_key: Routing key for the message
        datos_pedido_evento: Event payload dictionary

    Returns:
        True if published successfully, False otherwise
    """
    try:
        channel = await rabbitmq_connection.get_channel()

        # Get exchange (assumes it is already declared by consumers or startup)
        # Using get_exchange with ensure=False avoids the passive declare RPC call
        exchange = await channel.get_exchange(settings.RABBITMQ_DISPATCH_EXCHANGE, ensure=False)

        # Prepare message
        mensaje_json = json.dumps(datos_pedido_evento, default=str)
        message = Message(
            body=mensaje_json.encode(),
            delivery_mode=DeliveryMode.PERSISTENT,
            content_type="application/json",
        )

        # Publish
        await exchange.publish(message, routing_key=tipo_despacho_key)

        logger.info(
            f"Event published. Exchange: '{settings.RABBITMQ_DISPATCH_EXCHANGE}', RK: '{tipo_despacho_key}'"
        )
        logger.debug(f"Content: {mensaje_json[:250]}...")
        return True

    except Exception as e:
        logger.exception(f"Error publishing event: {e}")
        return False


async def close_producer_connection() -> None:
    """Close the producer connection (delegates to singleton)."""
    await rabbitmq_connection.close()
