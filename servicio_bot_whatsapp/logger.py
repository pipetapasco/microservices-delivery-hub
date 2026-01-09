import logging
import os
import sys

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
ENVIRONMENT = os.getenv("ENVIRONMENT", "production")

_log_level_map = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)

    if not logger.handlers:
        logger.setLevel(_log_level_map.get(LOG_LEVEL, logging.INFO))

        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(_log_level_map.get(LOG_LEVEL, logging.INFO))

        if ENVIRONMENT == "development":
            formatter = logging.Formatter(
                "[%(asctime)s] %(levelname)s %(name)s: %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
            )
        else:
            formatter = logging.Formatter("%(levelname)s %(name)s: %(message)s")

        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.propagate = False

    return logger
