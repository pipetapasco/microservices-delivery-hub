# servicio_pedidos/app/consumers/async_order_consumer.py
"""
Async RabbitMQ consumer for new order events using aio-pika.
"""
import asyncio
import contextlib
import json

from aio_pika import IncomingMessage

from ..core.config import settings
from ..core.logging_config import get_logger
from ..db.session import AsyncSessionLocal
from ..models.order_models import OrderCreateRequest
from ..services import order_service
from ..services.rabbitmq_connection import rabbitmq_connection

logger = get_logger(__name__)

_consumer_task: asyncio.Task | None = None
_should_stop = False


async def process_order_message(message: IncomingMessage) -> None:
    """Process an incoming order message."""
    try:
        async with message.process():
            body = message.body.decode("utf-8")
            logger.info(f"Order message received. Routing key: {message.routing_key}")

            try:
                datos_pedido = json.loads(body)
            except json.JSONDecodeError:
                logger.error(f"Message is not valid JSON: {body[:200]}...")
                # We return here, which exits the context manager successfully (ACK)
                # because this message is unprocessable.
                return

            logger.debug(
                f"Order data: {datos_pedido.get('tipo_servicio')}, Client: {datos_pedido.get('nombre_cliente')}"
            )

            order_in = OrderCreateRequest(**datos_pedido)

            # Create async session for this message
            async with AsyncSessionLocal() as db:
                db_order = await order_service.create_new_order(db=db, order_in=order_in)

                if db_order:
                    logger.info(f"Order ID {db_order.id_pedido} created from RabbitMQ event")
                else:
                    # Logic error or data issue, but we processed it.
                    logger.error(f"Failed to create order from event. Payload: {datos_pedido}")
                    # Decide if we want to ACK or NACK here.
                    # If it's a logic error, retrying might not help, so ACK is likely safe.
                    # If it was a DB error, create_new_order should have raised it (if we remove try/except there too)
                    # OR returned None.
                    # For now, let's assume if it returns None it's a "soft" failure that we ACK.

    except Exception as e:
        # This catch block is OUTSIDE message.process().
        # If an exception bubbles up here (e.g. DB connection lost),
        # message.process() will NOT have sent an ACK.
        # aio-pika will see the exception and NACK/requeue the message suitable for retry.
        logger.exception(f"Error processing order message (Requeueing): {e}")
        raise


async def start_order_consumer() -> None:
    """Start consuming order messages asynchronously."""
    global _should_stop
    _should_stop = False

    try:
        channel = await rabbitmq_connection.get_channel()

        # Declare exchange
        exchange = await channel.declare_exchange(
            settings.RABBITMQ_PEDIDOS_EXCHANGE, "direct", durable=True
        )

        # Declare queue
        queue = await channel.declare_queue(settings.RABBITMQ_PEDIDOS_QUEUE, durable=True)

        # Bind queue to exchange
        await queue.bind(exchange, routing_key=settings.RABBITMQ_PEDIDOS_ROUTING_KEY)

        logger.info(f"Order consumer started. Queue: '{settings.RABBITMQ_PEDIDOS_QUEUE}'")

        # Start consuming
        async with queue.iterator() as queue_iter:
            async for message in queue_iter:
                if _should_stop:
                    break
                await process_order_message(message)

    except asyncio.CancelledError:
        logger.info("Order consumer cancelled")
        raise
    except Exception as e:
        logger.exception(f"Order consumer error: {e}")
        raise


def create_order_consumer_task() -> asyncio.Task:
    """Create and return the consumer task."""
    global _consumer_task
    _consumer_task = asyncio.create_task(start_order_consumer())
    return _consumer_task


async def stop_order_consumer() -> None:
    """Stop the order consumer gracefully."""
    global _should_stop, _consumer_task
    _should_stop = True

    if _consumer_task and not _consumer_task.done():
        _consumer_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await _consumer_task
        _consumer_task = None

    logger.info("Order consumer stopped")
