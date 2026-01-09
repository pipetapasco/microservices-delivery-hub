import logging
import sys


def get_logger(name: str, level: int | None = None) -> logging.Logger:
    """
    Obtiene un logger configurado para el servicio de mototaxis.

    Args:
        name: Nombre del módulo o componente (ej: 'auth_service', 'crud_driver')
        level: Nivel de logging opcional. Por defecto usa INFO.

    Returns:
        Logger configurado con formato estructurado.
    """
    logger = logging.getLogger(f"mototaxis.{name}")

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(
            "[%(asctime)s] %(levelname)s [%(name)s]: %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(level or logging.INFO)
        logger.propagate = False

    return logger
