import uuid
from datetime import datetime

from ..core.logger import get_logger
from ..crud import crud_location_redis
from ..models.location_models import DriverLocation, LocationData

logger = get_logger("location_service")


async def update_driver_realtime_location(
    driver_id: uuid.UUID, location_data: LocationData
) -> bool:
    """
    Procesa y actualiza la ubicación en tiempo real de un conductor.
    Llama a la capa CRUD para interactuar con Redis.
    """
    logger.debug(f"Actualizando ubicación para conductor ID: {driver_id}")

    success = await crud_location_redis.update_driver_location(
        driver_id=driver_id, location_data=location_data
    )

    if success:
        logger.debug(f"Ubicación para conductor ID: {driver_id} procesada y actualizada en Redis.")
    else:
        logger.warning(f"Fallo al actualizar ubicación para conductor ID: {driver_id} en Redis.")

    return success


async def get_driver_location(driver_id: uuid.UUID) -> DriverLocation | None:
    """
    Obtiene la ubicación actual de un conductor.
    """
    logger.debug(f"Solicitando ubicación para conductor ID: {driver_id}")
    location_coords = await crud_location_redis.get_driver_current_location(driver_id=driver_id)

    if location_coords:
        return DriverLocation(
            id_conductor=driver_id,
            longitude=location_coords[0],
            latitude=location_coords[1],
            last_updated=datetime.utcnow(),
        )
    return None


async def find_nearby_drivers_service(
    longitude: float,
    latitude: float,
    radius_km: float,
    count: int | None = 5,
) -> list[DriverLocation]:
    """
    Encuentra conductores cercanos a un punto y los devuelve con un formato estructurado.
    """
    logger.info(
        f"Buscando conductores cercanos a Lon: {longitude}, Lat: {latitude}, Radio: {radius_km}km"
    )

    nearby_drivers_raw = await crud_location_redis.find_drivers_within_radius(
        longitude=longitude,
        latitude=latitude,
        radius_km=radius_km,
        count=count,
        with_dist=True,
        with_coord=True,
    )

    formatted_drivers: list[DriverLocation] = []
    if nearby_drivers_raw:
        for driver_info in nearby_drivers_raw:
            try:
                driver_id_str = driver_info[0]
                driver_info[1]
                coords = driver_info[2]

                formatted_drivers.append(
                    DriverLocation(
                        id_conductor=uuid.UUID(driver_id_str),
                        longitude=float(coords[0]),
                        latitude=float(coords[1]),
                        last_updated=datetime.utcnow(),
                    )
                )
            except Exception as e:
                logger.error(
                    f"Error procesando datos de conductor cercano: {driver_info}, error: {e}",
                    exc_info=True,
                )
                continue

    logger.info(f"{len(formatted_drivers)} conductores cercanos formateados encontrados.")
    return formatted_drivers
