"""Custom exceptions for the WhatsApp Bot service."""


class BotServiceError(Exception):
    """Base exception for all bot service errors."""

    pass


class ConfigurationError(BotServiceError):
    """Raised when required configuration is missing or invalid."""

    pass


class TwilioValidationError(BotServiceError):
    """Raised when Twilio signature validation fails."""

    pass


class RateLimitExceededError(BotServiceError):
    """Raised when rate limit is exceeded for a sender."""

    pass


class AudioProcessingError(BotServiceError):
    """Raised when audio download or transcription fails."""

    pass


class AudioSizeLimitError(AudioProcessingError):
    """Raised when audio file exceeds size limit."""

    pass


class InvalidMimeTypeError(AudioProcessingError):
    """Raised when media has invalid MIME type."""

    pass


class GeminiAnalysisError(BotServiceError):
    """Raised when Gemini AI analysis fails."""

    pass


class MessageQueueError(BotServiceError):
    """Raised when RabbitMQ operations fail."""

    pass


class SessionError(BotServiceError):
    """Raised when session operations fail."""

    pass


class RedisConnectionError(BotServiceError):
    """Raised when Redis connection fails."""

    pass
