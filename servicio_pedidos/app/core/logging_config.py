# servicio_pedidos/app/core/logging_config.py
import logging
import sys


def get_logger(name: str, level: int | None = None) -> logging.Logger:
    """
    Creates or retrieves a configured logger with structured formatting.

    Args:
        name: Logger name, typically __name__ of the calling module
        level: Optional logging level override (default: INFO)

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)

    if not logger.handlers:
        logger.setLevel(level or logging.INFO)

        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(level or logging.INFO)

        formatter = logging.Formatter(
            fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

        logger.propagate = False

    return logger
