"""
Simplified webhook that only validates and enqueues messages.
Processing is done by workers for scalability.
"""

import contextlib

from flask import Blueprint, Response, request
from twilio.request_validator import RequestValidator

import config
from core.exceptions import (
    ConfigurationError,
    MessageQueueError,
    RateLimitExceededError,
    TwilioValidationError,
)
from core.schemas import IncomingMessagePayload
from logger import get_logger
from services.rabbitmq_service import publish_incoming_message
from services.rate_limiter import get_rate_limiter

logger = get_logger(__name__)
webhook_bp = Blueprint("webhook", __name__)

_signature_validator = None


def _get_signature_validator() -> RequestValidator:
    """Get Twilio signature validator, fail if not configured."""
    global _signature_validator

    if _signature_validator is not None:
        return _signature_validator

    if not config.AUTH_TOKEN:
        raise ConfigurationError(
            "TWILIO_AUTH_TOKEN is required for webhook security. "
            "Refusing to run without signature validation."
        )

    _signature_validator = RequestValidator(config.AUTH_TOKEN)
    return _signature_validator


def _validate_twilio_signature() -> None:
    """Validate Twilio signature - fail closed."""
    validator = _get_signature_validator()

    signature = request.headers.get("X-Twilio-Signature", "")
    url = request.url
    post_vars = request.form.to_dict()

    if not validator.validate(url, post_vars, signature):
        logger.warning("Invalid Twilio signature rejected")
        raise TwilioValidationError("Invalid webhook signature")


def _validate_content_length() -> None:
    """Validate Content-Length to prevent DoS."""
    content_length = request.content_length or 0
    max_size = config.MAX_REQUEST_SIZE_BYTES

    if content_length > max_size:
        logger.warning(f"Request too large: {content_length} bytes")
        raise TwilioValidationError(f"Request exceeds maximum size of {max_size} bytes")


def _build_message_payload() -> dict:
    """Build and validate incoming message payload."""
    data = request.values

    num_media = 0
    with contextlib.suppress(ValueError, TypeError):
        num_media = int(data.get("NumMedia", 0))

    payload = IncomingMessagePayload(
        sender_number=data.get("From", ""),
        profile_name=data.get("ProfileName"),
        message_body=data.get("Body"),
        num_media=num_media,
        media_url=data.get("MediaUrl0") if num_media > 0 else None,
        media_content_type=data.get("MediaContentType0") if num_media > 0 else None,
    )

    return payload.model_dump(mode="json")


@webhook_bp.route("/webhook", methods=["POST"])
def webhook():
    """
    Webhook endpoint for Twilio WhatsApp messages.

    This endpoint:
    1. Validates Twilio signature (FAIL CLOSED - no token = reject all)
    2. Checks rate limit
    3. Validates payload
    4. Enqueues message for async processing
    5. Returns 200 immediately

    All processing happens in workers, not here.
    """
    try:
        _validate_content_length()
        _validate_twilio_signature()

        sender = request.values.get("From", request.remote_addr)
        rate_limiter = get_rate_limiter()
        rate_limiter.check_or_raise(sender)

        payload = _build_message_payload()

        if not payload.get("sender_number"):
            return Response("<Response/>", mimetype="text/xml")

        publish_incoming_message(payload)

        return Response("<Response/>", mimetype="text/xml")

    except ConfigurationError:
        logger.error("Configuration error in webhook", exc_info=True)
        return Response("Service Unavailable", status=503)

    except TwilioValidationError:
        logger.warning("Twilio validation failed", exc_info=True)
        return Response("Forbidden", status=403)

    except RateLimitExceededError:
        logger.warning("Rate limit exceeded", exc_info=True)
        return Response("<Response/>", mimetype="text/xml", status=429)

    except MessageQueueError:
        logger.error("Failed to enqueue message", exc_info=True)
        return Response("Service Unavailable", status=503)

    except Exception:
        logger.error("Unexpected webhook error", exc_info=True)
        return Response("Internal Server Error", status=500)


@webhook_bp.route("/health", methods=["GET"])
def health():
    """Health check endpoint."""
    from services.redis_client import redis_healthcheck

    redis_ok = redis_healthcheck()

    if redis_ok:
        return Response("OK", status=200)
    else:
        return Response("Unhealthy", status=503)
