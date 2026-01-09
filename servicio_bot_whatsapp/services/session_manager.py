"""Session manager using Redis for stateless scaling."""

import json
from datetime import datetime

from logger import get_logger

from core.exceptions import SessionError
from core.schemas import UserSession
from services.redis_client import get_redis_client

logger = get_logger(__name__)

SESSION_PREFIX = "session:"
SESSION_TTL_SECONDS = 3600


class SessionManager:
    """Manages user sessions in Redis."""

    def __init__(self):
        self._redis = get_redis_client()

    def _get_key(self, phone_number: str) -> str:
        """Generate Redis key for phone number."""
        safe_phone = phone_number.replace(":", "_").replace("+", "")
        return f"{SESSION_PREFIX}{safe_phone}"

    def get_session(self, phone_number: str) -> UserSession:
        """Get user session from Redis, create if not exists."""
        try:
            key = self._get_key(phone_number)
            data = self._redis.get(key)

            if data is None:
                return UserSession()

            session_dict = json.loads(data)
            session_dict["last_seen"] = datetime.fromisoformat(session_dict["last_seen"])
            return UserSession(**session_dict)

        except json.JSONDecodeError:
            logger.warning("Corrupted session data, creating new session")
            return UserSession()
        except Exception as e:
            logger.error(f"Error getting session: {type(e).__name__}")
            raise SessionError("Failed to get session") from e

    def save_session(self, phone_number: str, session: UserSession) -> None:
        """Save user session to Redis with TTL."""
        try:
            key = self._get_key(phone_number)
            session.last_seen = datetime.now()

            session_dict = session.model_dump()
            session_dict["last_seen"] = session_dict["last_seen"].isoformat()

            self._redis.setex(key, SESSION_TTL_SECONDS, json.dumps(session_dict))
        except Exception as e:
            logger.error(f"Error saving session: {type(e).__name__}")
            raise SessionError("Failed to save session") from e

    def clear_session(self, phone_number: str) -> None:
        """Clear user session from Redis."""
        try:
            key = self._get_key(phone_number)
            self._redis.delete(key)
        except Exception as e:
            logger.error(f"Error clearing session: {type(e).__name__}")

    def set_processing(self, phone_number: str, is_processing: bool) -> bool:
        """
        Set processing flag atomically. Returns True if flag was set successfully.
        Uses Redis SETNX for atomic check-and-set to prevent race conditions.
        """
        try:
            lock_key = f"processing_lock:{phone_number}"

            if is_processing:
                was_set = self._redis.setnx(lock_key, "1")
                if was_set:
                    self._redis.expire(lock_key, 300)
                return was_set
            else:
                self._redis.delete(lock_key)
                return True

        except Exception as e:
            logger.error(f"Error setting processing flag: {type(e).__name__}")
            return False

    def is_processing(self, phone_number: str) -> bool:
        """Check if a message is being processed for this user."""
        try:
            lock_key = f"processing_lock:{phone_number}"
            return self._redis.exists(lock_key) == 1
        except Exception:
            return False


_session_manager: SessionManager | None = None


def get_session_manager() -> SessionManager:
    """Get session manager singleton."""
    global _session_manager
    if _session_manager is None:
        _session_manager = SessionManager()
    return _session_manager
