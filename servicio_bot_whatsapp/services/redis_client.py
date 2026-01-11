"""Redis client singleton with connection pooling."""

import redis
from redis.exceptions import ConnectionError as RedisConnectionError

import config
from logger import get_logger

logger = get_logger(__name__)

_redis_client: redis.Redis | None = None


def get_redis_client() -> redis.Redis:
    """Get or create Redis client singleton with connection pool."""
    global _redis_client

    if _redis_client is not None:
        return _redis_client

    if not config.REDIS_URL:
        from core.exceptions import ConfigurationError

        raise ConfigurationError("REDIS_URL is required but not configured")

    try:
        _redis_client = redis.from_url(
            config.REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_keepalive=True,
            health_check_interval=30,
            retry_on_timeout=True,
        )
        _redis_client.ping()
        logger.info("Redis connection established")
        return _redis_client
    except RedisConnectionError as e:
        logger.error(f"Failed to connect to Redis: {type(e).__name__}")
        from core.exceptions import RedisConnectionError as AppRedisError

        raise AppRedisError("Cannot connect to Redis") from e


def close_redis_connection():
    """Close Redis connection."""
    global _redis_client
    if _redis_client is not None:
        try:
            _redis_client.close()
            logger.info("Redis connection closed")
        except Exception:
            pass
        _redis_client = None


def redis_healthcheck() -> bool:
    """Check if Redis is healthy."""
    try:
        client = get_redis_client()
        return client.ping()
    except Exception:
        return False
