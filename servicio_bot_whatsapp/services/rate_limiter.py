"""Rate limiter using Redis sliding window."""

import config
from logger import get_logger

from core.exceptions import RateLimitExceededError
from services.redis_client import get_redis_client

logger = get_logger(__name__)

RATE_LIMIT_PREFIX = "ratelimit:"


class RateLimiter:
    """Sliding window rate limiter using Redis."""

    def __init__(self, max_requests: int = 30, window_seconds: int = 60):
        self._redis = get_redis_client()
        self.max_requests = max_requests
        self.window_seconds = window_seconds

    def _get_key(self, identifier: str) -> str:
        """Generate Redis key for identifier."""
        safe_id = identifier.replace(":", "_").replace("+", "")
        return f"{RATE_LIMIT_PREFIX}{safe_id}"

    def is_allowed(self, identifier: str) -> bool:
        """
        Check if request is allowed under rate limit.
        Uses Redis sorted set for sliding window implementation.
        """
        import time

        try:
            key = self._get_key(identifier)
            current_time = time.time()
            window_start = current_time - self.window_seconds

            pipe = self._redis.pipeline()
            pipe.zremrangebyscore(key, 0, window_start)
            pipe.zcard(key)
            pipe.zadd(key, {str(current_time): current_time})
            pipe.expire(key, self.window_seconds + 1)
            results = pipe.execute()

            request_count = results[1]

            if request_count >= self.max_requests:
                logger.warning("Rate limit exceeded for identifier")
                return False

            return True

        except Exception as e:
            logger.error(f"Rate limiter error: {type(e).__name__}")
            return True

    def check_or_raise(self, identifier: str) -> None:
        """Check rate limit and raise exception if exceeded."""
        if not self.is_allowed(identifier):
            raise RateLimitExceededError(
                f"Rate limit exceeded: {self.max_requests} requests per {self.window_seconds}s"
            )


_rate_limiter = None


def get_rate_limiter() -> RateLimiter:
    """Get rate limiter singleton configured from environment."""
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter(
            max_requests=config.RATE_LIMIT_REQUESTS, window_seconds=config.RATE_LIMIT_WINDOW_SECONDS
        )
    return _rate_limiter
