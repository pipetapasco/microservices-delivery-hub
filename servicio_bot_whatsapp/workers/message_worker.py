"""Message worker - processes incoming WhatsApp messages from queue."""

import asyncio
import json

import config
from logger import get_logger

from core.exceptions import AudioProcessingError, GeminiAnalysisError, MessageQueueError
from core.schemas import IncomingMessagePayload
from services.audio_handler import get_audio_handler
from services.dialogue_manager import DialogueManager
from services.gemini_analyzer import analyze_message
from services.rabbitmq_service import _ensure_queue, get_consumer_channel, publish_order
from services.session_manager import get_session_manager
from services.twilio_client import get_auth_tuple, send_whatsapp_message

logger = get_logger(__name__)

_running = False


async def process_message(payload_dict: dict) -> None:
    """Process a single incoming message."""
    session_manager = get_session_manager()
    audio_handler = get_audio_handler()

    try:
        payload = IncomingMessagePayload(**payload_dict)
    except Exception:
        logger.error("Invalid message payload", exc_info=True)
        return

    sender = payload.sender_number

    if not session_manager.set_processing(sender, True):
        send_whatsapp_message(
            sender, "Estoy procesando tu solicitud, por favor espera un momento..."
        )
        return

    try:
        session = session_manager.get_session(sender)
        dialogue = DialogueManager(session, payload.profile_name)

        if dialogue.should_send_welcome():
            send_whatsapp_message(sender, dialogue.get_welcome_message())

        text_to_analyze: str | None = None

        if payload.num_media > 0 and payload.media_url:
            if payload.media_content_type and payload.media_content_type.startswith("audio/"):
                try:
                    auth = get_auth_tuple()
                    filepath = await audio_handler.download_audio(
                        payload.media_url, payload.media_content_type, auth
                    )
                    text_to_analyze = await audio_handler.transcribe(filepath)

                    if not text_to_analyze:
                        send_whatsapp_message(
                            sender, dialogue.get_error_message("audio_not_understood")
                        )
                        return

                except AudioProcessingError:
                    logger.error("Audio processing failed", exc_info=True)
                    send_whatsapp_message(sender, dialogue.get_error_message("audio_error"))
                    return
            else:
                send_whatsapp_message(sender, dialogue.get_error_message("unsupported_media"))
                return

        elif payload.message_body:
            text_to_analyze = payload.message_body

        else:
            if not dialogue.should_send_welcome():
                send_whatsapp_message(sender, dialogue.get_error_message("message_not_understood"))
            return

        if not text_to_analyze:
            return

        try:
            extracted = await analyze_message(text_to_analyze)
            dialogue.update_order_data(extracted)
        except GeminiAnalysisError:
            logger.error("Gemini analysis failed", exc_info=True)
            send_whatsapp_message(sender, dialogue.get_error_message("ai_error"))
            return

        is_complete, prompt_message = dialogue.get_next_prompt()

        if not is_complete:
            send_whatsapp_message(sender, prompt_message)
            session_manager.save_session(sender, session)
            return

        order = dialogue.build_order_payload(sender)

        try:
            publish_order(order.model_dump())
            send_whatsapp_message(sender, dialogue.get_confirmation_message(order.tipo_servicio))
        except MessageQueueError:
            logger.error("Failed to publish order", exc_info=True)
            send_whatsapp_message(sender, dialogue.get_error_message("order_failed"))
            return

        dialogue.clear_order()
        session_manager.save_session(sender, session)

    except Exception:
        logger.error("Unexpected error processing message", exc_info=True)
        raise
    finally:
        session_manager.set_processing(sender, False)


def on_message_callback(channel, method, properties, body):
    """
    Callback for RabbitMQ message consumption.
    Uses basic_nack with requeue=False to send failed messages to DLX.
    """
    try:
        payload = json.loads(body.decode("utf-8"))
        asyncio.run(process_message(payload))
        channel.basic_ack(delivery_tag=method.delivery_tag)

    except json.JSONDecodeError:
        logger.error("Invalid JSON in message - sending to DLX", exc_info=True)
        channel.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

    except Exception:
        logger.error("Error processing message - sending to DLX", exc_info=True)
        channel.basic_nack(delivery_tag=method.delivery_tag, requeue=False)


def start_worker():
    """Start the message processing worker."""
    global _running
    _running = True

    logger.info("Starting message worker...")

    try:
        with get_consumer_channel() as channel:
            _ensure_queue(
                channel,
                config.INCOMING_MESSAGES_QUEUE,
                config.INCOMING_MESSAGES_EXCHANGE,
                config.INCOMING_MESSAGES_ROUTING_KEY,
            )

            channel.basic_consume(
                queue=config.INCOMING_MESSAGES_QUEUE,
                on_message_callback=on_message_callback,
                auto_ack=False,
            )

            logger.info(f"Worker consuming from queue: {config.INCOMING_MESSAGES_QUEUE}")

            while _running:
                channel.connection.process_data_events(time_limit=1)

    except KeyboardInterrupt:
        logger.info("Worker stopped by user")
    except Exception:
        logger.error("Worker error", exc_info=True)
        raise


def stop_worker():
    """Stop the message processing worker."""
    global _running
    _running = False
    logger.info("Worker stop requested")
