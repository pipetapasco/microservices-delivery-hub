# servicio_pedidos/app/services/rabbitmq_connection.py
"""
Singleton connection manager for aio-pika RabbitMQ connections.
Provides shared connection and channel for all consumers and producers.
"""
from typing import Optional

import aio_pika
from aio_pika import Channel
from aio_pika.abc import AbstractRobustConnection

from ..core.config import settings
from ..core.logging_config import get_logger

logger = get_logger(__name__)


class RabbitMQConnection:
    """Singleton connection manager for RabbitMQ using aio-pika."""

    _instance: Optional["RabbitMQConnection"] = None
    _connection: AbstractRobustConnection | None = None
    _channel: Channel | None = None

    def __new__(cls) -> "RabbitMQConnection":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @property
    def is_connected(self) -> bool:
        return self._connection is not None and not self._connection.is_closed

    async def connect(self) -> AbstractRobustConnection:
        """Establish connection to RabbitMQ."""
        if self.is_connected:
            return self._connection

        try:
            connection_url = (
                f"amqp://{settings.RABBITMQ_USER}:{settings.RABBITMQ_PASSWORD}"
                f"@{settings.RABBITMQ_HOST}:{settings.RABBITMQ_PORT}/"
            )

            self._connection = await aio_pika.connect_robust(
                connection_url, connection_class=aio_pika.RobustConnection
            )

            logger.info(
                f"Connected to RabbitMQ at {settings.RABBITMQ_HOST}:{settings.RABBITMQ_PORT}"
            )
            return self._connection

        except Exception as e:
            logger.exception(f"Failed to connect to RabbitMQ: {e}")
            raise

    async def get_channel(self) -> Channel:
        """Get or create a channel."""
        if self._connection is None or self._connection.is_closed:
            await self.connect()

        if self._channel is None or self._channel.is_closed:
            self._channel = await self._connection.channel()
            logger.debug("RabbitMQ channel created")

        return self._channel

    async def close(self) -> None:
        """Close connection gracefully."""
        if self._channel and not self._channel.is_closed:
            await self._channel.close()
            self._channel = None
            logger.debug("RabbitMQ channel closed")

        if self._connection and not self._connection.is_closed:
            await self._connection.close()
            self._connection = None
            logger.info("RabbitMQ connection closed")


# Singleton instance
rabbitmq_connection = RabbitMQConnection()
