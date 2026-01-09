"""Thread-safe RabbitMQ service with connection pooling and DLX support."""

import json
import threading
from contextlib import contextmanager, suppress

import config
import pika
from logger import get_logger
from pika.exceptions import AMQPChannelError, AMQPConnectionError

from core.exceptions import MessageQueueError

logger = get_logger(__name__)

_thread_local = threading.local()


def _get_connection_params() -> pika.ConnectionParameters:
    """Build RabbitMQ connection parameters with resilient timeouts."""
    credentials = pika.PlainCredentials(config.RABBITMQ_USER, config.RABBITMQ_PASSWORD)
    return pika.ConnectionParameters(
        host=config.RABBITMQ_HOST,
        port=config.RABBITMQ_PORT,
        credentials=credentials,
        heartbeat=config.RABBITMQ_HEARTBEAT,
        blocked_connection_timeout=config.RABBITMQ_BLOCKED_CONNECTION_TIMEOUT,
        connection_attempts=3,
        retry_delay=5,
    )


def _get_thread_channel() -> pika.channel.Channel:
    """
    Get RabbitMQ channel for current thread.
    Each thread gets its own connection and channel for thread-safety.
    """
    if (
        not hasattr(_thread_local, "connection")
        or _thread_local.connection is None
        or _thread_local.connection.is_closed
    ):
        try:
            params = _get_connection_params()
            _thread_local.connection = pika.BlockingConnection(params)
            _thread_local.channel = _thread_local.connection.channel()
            logger.info("RabbitMQ connection established for thread")
        except AMQPConnectionError:
            logger.error("Failed to connect to RabbitMQ", exc_info=True)
            raise MessageQueueError("Cannot connect to RabbitMQ")

    if (
        not hasattr(_thread_local, "channel")
        or _thread_local.channel is None
        or _thread_local.channel.is_closed
    ):
        _thread_local.channel = _thread_local.connection.channel()

    return _thread_local.channel


def _ensure_queue_with_dlx(
    channel: pika.channel.Channel, queue_name: str, exchange: str, routing_key: str
) -> None:
    """
    Ensure exchange, queue, binding, and Dead Letter infrastructure exist.
    Messages that fail processing will be routed to the DLX instead of being requeued infinitely.
    """
    dlx_exchange = f"{exchange}_dlx"
    dlx_queue = f"{queue_name}_dlx"
    dlx_routing_key = f"{routing_key}.dead"

    channel.exchange_declare(exchange=dlx_exchange, exchange_type="direct", durable=True)

    channel.queue_declare(queue=dlx_queue, durable=True)

    channel.queue_bind(exchange=dlx_exchange, queue=dlx_queue, routing_key=dlx_routing_key)

    channel.exchange_declare(exchange=exchange, exchange_type="direct", durable=True)

    channel.queue_declare(
        queue=queue_name,
        durable=True,
        arguments={
            "x-dead-letter-exchange": dlx_exchange,
            "x-dead-letter-routing-key": dlx_routing_key,
        },
    )

    channel.queue_bind(exchange=exchange, queue=queue_name, routing_key=routing_key)


def _ensure_queue(
    channel: pika.channel.Channel, queue_name: str, exchange: str, routing_key: str
) -> None:
    """Ensure exchange, queue, and binding exist with DLX support."""
    _ensure_queue_with_dlx(channel, queue_name, exchange, routing_key)


def publish_incoming_message(payload: dict) -> bool:
    """
    Publish incoming WhatsApp message to processing queue.
    This is called by the webhook to enqueue messages for workers.
    """
    try:
        channel = _get_thread_channel()

        _ensure_queue(
            channel,
            config.INCOMING_MESSAGES_QUEUE,
            config.INCOMING_MESSAGES_EXCHANGE,
            config.INCOMING_MESSAGES_ROUTING_KEY,
        )

        channel.basic_publish(
            exchange=config.INCOMING_MESSAGES_EXCHANGE,
            routing_key=config.INCOMING_MESSAGES_ROUTING_KEY,
            body=json.dumps(payload),
            properties=pika.BasicProperties(
                delivery_mode=pika.spec.PERSISTENT_DELIVERY_MODE, content_type="application/json"
            ),
        )
        return True

    except (AMQPConnectionError, AMQPChannelError):
        logger.error("RabbitMQ error publishing message", exc_info=True)
        _close_thread_connection()
        raise MessageQueueError("Failed to publish message")
    except Exception:
        logger.error("Unexpected error publishing message", exc_info=True)
        raise MessageQueueError("Failed to publish message")


def publish_order(order_payload: dict) -> bool:
    """Publish completed order to orders queue."""
    try:
        channel = _get_thread_channel()

        _ensure_queue(
            channel,
            config.RABBITMQ_PEDIDOS_QUEUE,
            config.RABBITMQ_PEDIDOS_EXCHANGE,
            config.RABBITMQ_PEDIDOS_ROUTING_KEY,
        )

        channel.basic_publish(
            exchange=config.RABBITMQ_PEDIDOS_EXCHANGE,
            routing_key=config.RABBITMQ_PEDIDOS_ROUTING_KEY,
            body=json.dumps(order_payload),
            properties=pika.BasicProperties(
                delivery_mode=pika.spec.PERSISTENT_DELIVERY_MODE, content_type="application/json"
            ),
        )
        return True

    except (AMQPConnectionError, AMQPChannelError):
        logger.error("RabbitMQ error publishing order", exc_info=True)
        _close_thread_connection()
        raise MessageQueueError("Failed to publish order")
    except Exception:
        logger.error("Unexpected error publishing order", exc_info=True)
        raise MessageQueueError("Failed to publish order")


@contextmanager
def get_consumer_channel():
    """
    Context manager for consuming messages.
    Creates a dedicated connection for consumers.
    """
    connection = None
    channel = None
    try:
        params = _get_connection_params()
        connection = pika.BlockingConnection(params)
        channel = connection.channel()
        channel.basic_qos(prefetch_count=1)
        yield channel
    except AMQPConnectionError:
        logger.error("Failed to create consumer connection", exc_info=True)
        raise MessageQueueError("Cannot connect to RabbitMQ for consuming")
    finally:
        if channel and channel.is_open:
            with suppress(Exception):
                channel.close()
        if connection and connection.is_open:
            with suppress(Exception):
                connection.close()


def _close_thread_connection():
    """Close connection for current thread."""
    if hasattr(_thread_local, "channel") and _thread_local.channel:
        with suppress(Exception):
            _thread_local.channel.close()
        _thread_local.channel = None

    if hasattr(_thread_local, "connection") and _thread_local.connection:
        with suppress(Exception):
            _thread_local.connection.close()
        _thread_local.connection = None


def close_all_connections():
    """Close all RabbitMQ connections (called on shutdown)."""
    _close_thread_connection()
    logger.info("RabbitMQ connections closed")
