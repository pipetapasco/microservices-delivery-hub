"""Twilio client for sending WhatsApp messages."""

import config
from logger import get_logger
from twilio.base.exceptions import TwilioRestException
from twilio.rest import Client

from core.exceptions import ConfigurationError

logger = get_logger(__name__)

_twilio_client: Client | None = None


def _get_client() -> Client:
    """Get or create Twilio client."""
    global _twilio_client

    if _twilio_client is not None:
        return _twilio_client

    if not config.ACCOUNT_SID or not config.AUTH_TOKEN:
        raise ConfigurationError("Twilio credentials not configured")

    try:
        _twilio_client = Client(config.ACCOUNT_SID, config.AUTH_TOKEN)
        return _twilio_client
    except Exception as e:
        logger.error(f"Failed to create Twilio client: {type(e).__name__}")
        raise ConfigurationError("Cannot initialize Twilio client") from e


def send_whatsapp_message(to_number: str, message_body: str) -> bool:
    """
    Send WhatsApp message via Twilio.
    Returns True if successful.
    """
    if not config.TWILIO_WHATSAPP_NUMBER:
        logger.error("TWILIO_WHATSAPP_NUMBER not configured")
        return False

    if not to_number or not message_body:
        logger.error("Missing to_number or message_body")
        return False

    try:
        client = _get_client()
        client.messages.create(
            from_=config.TWILIO_WHATSAPP_NUMBER, body=message_body[:1600], to=to_number
        )
        return True

    except TwilioRestException as e:
        logger.error(f"Twilio API error: {e.code}")
        return False
    except ConfigurationError:
        return False
    except Exception as e:
        logger.error(f"Error sending message: {type(e).__name__}")
        return False


def get_auth_tuple() -> tuple | None:
    """Get auth tuple for downloading media from Twilio."""
    if config.ACCOUNT_SID and config.AUTH_TOKEN:
        return (config.ACCOUNT_SID, config.AUTH_TOKEN)
    return None
