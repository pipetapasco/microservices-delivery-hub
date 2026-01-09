"""Worker entry point - processes messages from queue."""

import signal
import sys

import config
from logger import get_logger

from services.rabbitmq_service import close_all_connections
from services.redis_client import close_redis_connection
from workers.message_worker import start_worker, stop_worker

logger = get_logger(__name__)


def signal_handler(signum, frame):
    """Handle shutdown signals gracefully."""
    logger.info(f"Received signal {signum}, shutting down...")
    stop_worker()
    close_redis_connection()
    close_all_connections()
    sys.exit(0)


def main():
    """Main entry point for worker."""
    config.validate_worker_config()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    logger.info("Starting message processing worker...")

    try:
        start_worker()
    except KeyboardInterrupt:
        logger.info("Worker interrupted")
    except Exception as e:
        logger.error(f"Worker failed: {type(e).__name__}")
        sys.exit(1)
    finally:
        close_redis_connection()
        close_all_connections()


if __name__ == "__main__":
    main()
