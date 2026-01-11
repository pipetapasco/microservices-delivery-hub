import asyncio
import contextlib
import json

import pika

import config
from logger import get_logger
from services.twilio_service import enviar_mensaje_whatsapp

logger = get_logger(__name__)

_client_notif_connection = None
_client_notif_channel = None
_client_notif_consumer_tag = None

MAX_MESSAGE_LENGTH = 1600


def _sanitize_message(message: str) -> str:
    if not message:
        return ""
    return message.strip()[:MAX_MESSAGE_LENGTH]


async def process_client_notification_event(message_body_str: str):
    try:
        evento_data = json.loads(message_body_str)

        id_cliente_externo = evento_data.get("id_cliente_externo")
        mensaje_para_cliente = evento_data.get("mensaje_para_cliente")

        if not id_cliente_externo or not mensaje_para_cliente:
            logger.error("Incomplete notification event data: missing required fields")
            return

        mensaje_sanitizado = _sanitize_message(mensaje_para_cliente)
        enviar_mensaje_whatsapp(to_number=id_cliente_externo, message_body=mensaje_sanitizado)

    except json.JSONDecodeError:
        logger.error("Invalid JSON in notification message")
    except Exception as e:
        logger.error(f"Error processing notification event: {type(e).__name__}")


def on_client_notification_message_callback(channel, method, properties, body):
    try:
        message_body_str = body.decode("utf-8")
        asyncio.run(process_client_notification_event(message_body_str))
    except UnicodeDecodeError:
        logger.error("Invalid encoding in message body")
    finally:
        channel.basic_ack(delivery_tag=method.delivery_tag)


def start_client_notification_consumer():
    global _client_notif_connection, _client_notif_channel, _client_notif_consumer_tag
    try:
        credentials = pika.PlainCredentials(config.RABBITMQ_USER, config.RABBITMQ_PASSWORD)
        parameters = pika.ConnectionParameters(
            host=config.RABBITMQ_HOST,
            port=config.RABBITMQ_PORT,
            credentials=credentials,
            heartbeat=600,
            blocked_connection_timeout=300,
            connection_attempts=3,
            retry_delay=5,
        )
        _client_notif_connection = pika.BlockingConnection(parameters)
        _client_notif_channel = _client_notif_connection.channel()

        _client_notif_channel.exchange_declare(
            exchange=config.RABBITMQ_DISPATCH_EXCHANGE, exchange_type="direct", durable=True
        )

        result = _client_notif_channel.queue_declare(
            queue=config.RABBITMQ_CLIENT_NOTIFICATION_QUEUE, durable=True
        )
        queue_name = result.method.queue

        _client_notif_channel.queue_bind(
            exchange=config.RABBITMQ_DISPATCH_EXCHANGE,
            queue=queue_name,
            routing_key=config.RABBITMQ_NOTIFY_CLIENT_ROUTING_KEY,
        )

        _client_notif_consumer_tag = _client_notif_channel.basic_consume(
            queue=queue_name,
            on_message_callback=on_client_notification_message_callback,
            auto_ack=False,
        )
        _client_notif_channel.start_consuming()
    except pika.exceptions.AMQPConnectionError:
        logger.error("RabbitMQ connection failed")
    except KeyboardInterrupt:
        logger.info("Consumer stopped manually")
    except Exception as e:
        logger.error(f"Unexpected consumer error: {type(e).__name__}")
    finally:
        stop_client_notification_consumer()


def stop_client_notification_consumer():
    global _client_notif_connection, _client_notif_channel, _client_notif_consumer_tag
    if _client_notif_channel and _client_notif_channel.is_open and _client_notif_consumer_tag:
        with contextlib.suppress(Exception):
            _client_notif_channel.basic_cancel(consumer_tag=_client_notif_consumer_tag)
    if _client_notif_channel and _client_notif_channel.is_open:
        with contextlib.suppress(Exception):
            _client_notif_channel.close()
    if _client_notif_connection and _client_notif_connection.is_open:
        with contextlib.suppress(Exception):
            _client_notif_connection.close()
    _client_notif_channel = None
    _client_notif_connection = None
    _client_notif_consumer_tag = None
