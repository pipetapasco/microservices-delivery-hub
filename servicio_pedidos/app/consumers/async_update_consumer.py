# servicio_pedidos/app/consumers/async_update_consumer.py
"""
Async RabbitMQ consumer for order update events using aio-pika.
"""
import asyncio
import contextlib
import json
import uuid

from aio_pika import IncomingMessage

from ..core.config import settings
from ..core.logging_config import get_logger
from ..db.session import AsyncSessionLocal
from ..models.order_models import OrderUpdateRequest
from ..services import order_service, rabbitmq_producer_service
from ..services.rabbitmq_connection import rabbitmq_connection

logger = get_logger(__name__)

_consumer_task: asyncio.Task | None = None
_should_stop = False


async def process_update_message(message: IncomingMessage) -> None:
    """Process an incoming order update message."""
    try:
        async with message.process():
            body = message.body.decode("utf-8")
            logger.info(f"Update message received. Routing key: {message.routing_key}")

            try:
                evento_data = json.loads(body)
            except json.JSONDecodeError:
                logger.error(f"Message is not valid JSON: {body[:200]}...")
                return

            logger.debug(f"Event data: {evento_data}")

            id_pedido_str = evento_data.get("id_pedido")
            id_conductor_str = evento_data.get("id_conductor_que_acepto")
            nuevo_estado = evento_data.get("nuevo_estado_para_pedido")
            nombre_conductor = evento_data.get("nombre_conductor")
            placa_vehiculo = evento_data.get("placa_vehiculo_activa")

            if not all([id_pedido_str, id_conductor_str, nuevo_estado]):
                logger.error(f"Incomplete update event data: {evento_data}")
                return

            try:
                id_pedido_uuid = uuid.UUID(id_pedido_str)
                id_conductor_uuid = uuid.UUID(id_conductor_str)
            except ValueError:
                logger.error("Event IDs are not valid UUIDs")
                return

            async with AsyncSessionLocal() as db:
                order_update_payload = OrderUpdateRequest(
                    estado_pedido=nuevo_estado, id_conductor_asignado=id_conductor_uuid
                )

                updated_order = await order_service.update_order_by_id(
                    db=db,
                    order_id=id_pedido_uuid,
                    order_update_in=order_update_payload,
                    actor_tipo="conductor_acepta",
                    actor_id=str(id_conductor_uuid),
                )

                if updated_order and updated_order.estado_pedido == "asignado_conductor":
                    logger.info(
                        f"Order {updated_order.id_pedido} updated with driver {updated_order.id_conductor_asignado}"
                    )

                    # Publish client notification
                    evento_cliente = {
                        "id_pedido": str(updated_order.id_pedido),
                        "id_cliente_externo": updated_order.id_cliente_externo,
                        "nombre_cliente": updated_order.nombre_cliente,
                        "tipo_servicio": updated_order.tipo_servicio,
                        "estado_actual_pedido": updated_order.estado_pedido,
                        "nombre_conductor_asignado": nombre_conductor,
                        "placa_vehiculo_conductor": placa_vehiculo,
                        "mensaje_para_cliente": (
                            f"¡Buenas noticias! Tu conductor {nombre_conductor or 'asignado'} "
                            f"(vehículo {placa_vehiculo or 'en camino'}) "
                            f"está en camino para tu servicio de {updated_order.tipo_servicio}."
                        ),
                    }

                    await rabbitmq_producer_service.publicar_evento_pedido_para_despacho(
                        tipo_despacho_key=settings.RABBITMQ_NOTIFY_CLIENT_ROUTING_KEY,
                        datos_pedido_evento=evento_cliente,
                    )
                else:
                    logger.warning(f"Failed to update order {id_pedido_uuid}")

    except Exception as e:
        logger.exception(f"Error processing update message (Requeueing): {e}")
        raise


async def start_update_consumer() -> None:
    """Start consuming update messages asynchronously."""
    global _should_stop
    _should_stop = False

    try:
        channel = await rabbitmq_connection.get_channel()

        # Declare exchange
        exchange = await channel.declare_exchange(
            settings.RABBITMQ_DISPATCH_EXCHANGE, "direct", durable=True
        )

        # Declare queue
        queue = await channel.declare_queue(settings.RABBITMQ_ORDER_UPDATES_QUEUE, durable=True)

        # Bind queue
        await queue.bind(exchange, routing_key=settings.RABBITMQ_ORDER_UPDATE_ROUTING_KEY)

        logger.info(f"Update consumer started. Queue: '{settings.RABBITMQ_ORDER_UPDATES_QUEUE}'")

        # Start consuming
        async with queue.iterator() as queue_iter:
            async for message in queue_iter:
                if _should_stop:
                    break
                await process_update_message(message)

    except asyncio.CancelledError:
        logger.info("Update consumer cancelled")
        raise
    except Exception as e:
        logger.exception(f"Update consumer error: {e}")
        raise


def create_update_consumer_task() -> asyncio.Task:
    """Create and return the consumer task."""
    global _consumer_task
    _consumer_task = asyncio.create_task(start_update_consumer())
    return _consumer_task


async def stop_update_consumer() -> None:
    """Stop the update consumer gracefully."""
    global _should_stop, _consumer_task
    _should_stop = True

    if _consumer_task and not _consumer_task.done():
        _consumer_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await _consumer_task
        _consumer_task = None

    logger.info("Update consumer stopped")
