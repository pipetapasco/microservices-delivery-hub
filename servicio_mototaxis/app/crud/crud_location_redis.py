import asyncio
import uuid
from typing import Any

import redis

from ..core.config import settings
from ..core.logger import get_logger
from ..db.session import get_redis_client
from ..models.location_models import LocationData

logger = get_logger("crud_location_redis")

DRIVER_LOCATIONS_GEO_KEY = settings.REDIS_DRIVER_LOCATIONS_KEY


async def update_driver_location(driver_id: uuid.UUID, location_data: LocationData) -> bool:
    """
    Añade o actualiza la ubicación de un conductor en el conjunto geoespacial de Redis.
    El 'member' en el conjunto GEO será el ID del conductor convertido a string.
    """
    r = get_redis_client()
    if not r:
        logger.error(
            f"Cliente Redis no disponible. No se puede actualizar ubicación para conductor ID: {driver_id}"
        )
        return False

    try:
        driver_id_str = str(driver_id)

        await asyncio.to_thread(
            r.geoadd,
            DRIVER_LOCATIONS_GEO_KEY,
            (location_data.longitude, location_data.latitude, driver_id_str),
        )

        logger.debug(
            f"Ubicación actualizada para conductor ID: {driver_id} -> Lon: {location_data.longitude}, Lat: {location_data.latitude}"
        )
        return True
    except redis.exceptions.RedisError as e:
        logger.error(
            f"Error de Redis al actualizar ubicación para conductor ID {driver_id}: {e}",
            exc_info=True,
        )
        return False
    except Exception as e:
        logger.error(
            f"Error inesperado al actualizar ubicación para conductor ID {driver_id}: {e}",
            exc_info=True,
        )
        return False


async def get_driver_current_location(driver_id: uuid.UUID) -> tuple[float, float] | None:
    """
    Obtiene la longitud y latitud actuales de un conductor desde Redis.
    Devuelve una tupla (longitude, latitude) o None si no se encuentra.
    """
    r = get_redis_client()
    if not r:
        logger.error(
            f"Cliente Redis no disponible. No se puede obtener ubicación para conductor ID: {driver_id}"
        )
        return None

    try:
        driver_id_str = str(driver_id)
        position = await asyncio.to_thread(r.geopos, DRIVER_LOCATIONS_GEO_KEY, driver_id_str)

        if position and position[0] is not None:
            longitude, latitude = position[0]
            logger.debug(
                f"Ubicación obtenida para conductor ID: {driver_id} -> Lon: {longitude}, Lat: {latitude}"
            )
            return (float(longitude), float(latitude))
        else:
            logger.debug(f"Ubicación no encontrada para conductor ID: {driver_id}")
            return None
    except redis.exceptions.RedisError as e:
        logger.error(
            f"Error de Redis al obtener ubicación para conductor ID {driver_id}: {e}", exc_info=True
        )
        return None
    except Exception as e:
        logger.error(
            f"Error inesperado al obtener ubicación para conductor ID {driver_id}: {e}",
            exc_info=True,
        )
        return None


async def find_drivers_within_radius(
    longitude: float,
    latitude: float,
    radius_km: float,
    count: int | None = None,
    with_dist: bool = False,
    with_coord: bool = False,
) -> list[Any]:
    """
    Encuentra conductores dentro de un radio específico desde un punto central.
    """
    r = get_redis_client()
    if not r:
        logger.error("Cliente Redis no disponible. No se pueden buscar conductores cercanos.")
        return []

    try:
        logger.debug(
            f"Buscando conductores dentro de {radius_km}km de Lon: {longitude}, Lat: {latitude}"
        )

        nearby_drivers = await asyncio.to_thread(
            r.georadius,
            DRIVER_LOCATIONS_GEO_KEY,
            longitude,
            latitude,
            radius_km,
            unit="km",
            withdist=with_dist,
            withcoord=with_coord,
            count=count,
            sort="ASC",
        )

        logger.debug(f"Conductores encontrados: {len(nearby_drivers) if nearby_drivers else 0}")
        return nearby_drivers if nearby_drivers else []
    except redis.exceptions.RedisError as e:
        logger.error(f"Error de Redis al buscar conductores cercanos: {e}", exc_info=True)
        return []
    except Exception as e:
        logger.error(f"Error inesperado al buscar conductores cercanos: {e}", exc_info=True)
        return []


async def remove_driver_location(driver_id: uuid.UUID) -> bool:
    """
    Elimina la ubicación de un conductor del conjunto geoespacial de Redis.
    Esto podría usarse si un conductor se desconecta o se da de baja.
    """
    r = get_redis_client()
    if not r:
        logger.error(
            f"Cliente Redis no disponible. No se puede eliminar ubicación para conductor ID: {driver_id}"
        )
        return False

    try:
        driver_id_str = str(driver_id)
        result = await asyncio.to_thread(r.zrem, DRIVER_LOCATIONS_GEO_KEY, driver_id_str)

        if result > 0:
            logger.info(f"Ubicación eliminada para conductor ID: {driver_id}")
            return True
        else:
            logger.debug(
                f"Ubicación no encontrada para eliminar para conductor ID: {driver_id} (o ya eliminada)."
            )
            return False
    except redis.exceptions.RedisError as e:
        logger.error(
            f"Error de Redis al eliminar ubicación para conductor ID {driver_id}: {e}",
            exc_info=True,
        )
        return False
    except Exception as e:
        logger.error(
            f"Error inesperado al eliminar ubicación para conductor ID {driver_id}: {e}",
            exc_info=True,
        )
        return False
