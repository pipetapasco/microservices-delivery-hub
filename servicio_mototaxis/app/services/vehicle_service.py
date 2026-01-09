import asyncio
import uuid

from sqlalchemy.orm import Session

from ..core.logger import get_logger
from ..crud import crud_vehicle
from ..db.models_db import VehiculoConductorDB
from ..models.driver_models import VehicleCreate, VehicleUpdate

logger = get_logger("vehicle_service")


async def add_new_vehicle(
    db: Session, *, driver_id: uuid.UUID, vehicle_in: VehicleCreate
) -> VehiculoConductorDB | None:
    """Añade un nuevo vehículo para un conductor."""
    logger.info(f"Añadiendo vehículo para conductor: {driver_id}")
    try:
        new_vehicle = await asyncio.to_thread(
            crud_vehicle.create_driver_vehicle, db, vehicle_in=vehicle_in, driver_id=driver_id
        )
        logger.info(f"Vehículo creado con ID: {new_vehicle.id_vehiculo}")
        return new_vehicle
    except Exception as e:
        logger.error(f"Error creando vehículo para conductor {driver_id}: {e}", exc_info=True)
        raise


async def get_all_driver_vehicles(
    db: Session, *, driver_id: uuid.UUID, skip: int = 0, limit: int = 100
) -> list[VehiculoConductorDB]:
    """Obtiene todos los vehículos de un conductor."""
    return await asyncio.to_thread(
        crud_vehicle.get_driver_vehicles, db, driver_id=driver_id, skip=skip, limit=limit
    )


async def get_vehicle_by_id_for_driver(
    db: Session, *, vehicle_id: uuid.UUID, driver_id: uuid.UUID
) -> VehiculoConductorDB | None:
    """Obtiene un vehículo específico de un conductor."""
    return await asyncio.to_thread(
        crud_vehicle.get_driver_vehicle_by_id, db, vehicle_id=vehicle_id, driver_id=driver_id
    )


async def update_existing_vehicle(
    db: Session, *, vehicle_id: uuid.UUID, vehicle_in: VehicleUpdate, driver_id: uuid.UUID
) -> VehiculoConductorDB | None:
    """Actualiza un vehículo existente de un conductor."""
    logger.info(f"Actualizando vehículo {vehicle_id} para conductor: {driver_id}")
    db_vehicle = await get_vehicle_by_id_for_driver(
        db=db, vehicle_id=vehicle_id, driver_id=driver_id
    )
    if not db_vehicle:
        logger.warning(f"Vehículo {vehicle_id} no encontrado para conductor {driver_id}")
        return None
    try:
        updated_vehicle = await asyncio.to_thread(
            crud_vehicle.update_driver_vehicle, db, db_vehicle_obj=db_vehicle, vehicle_in=vehicle_in
        )
        return updated_vehicle
    except Exception as e:
        logger.error(f"Error actualizando vehículo {vehicle_id}: {e}", exc_info=True)
        raise


async def delete_vehicle_from_driver(
    db: Session, *, vehicle_id: uuid.UUID, driver_id: uuid.UUID
) -> bool:
    """Elimina un vehículo de un conductor."""
    logger.info(f"Eliminando vehículo {vehicle_id} para conductor: {driver_id}")
    try:
        result = await asyncio.to_thread(
            crud_vehicle.delete_driver_vehicle, db, vehicle_id=vehicle_id, driver_id=driver_id
        )
        return result
    except Exception as e:
        logger.error(f"Error eliminando vehículo {vehicle_id}: {e}", exc_info=True)
        raise


async def set_driver_active_vehicle(
    db: Session, *, vehicle_id: uuid.UUID, driver_id: uuid.UUID
) -> VehiculoConductorDB | None:
    """Marca un vehículo como activo para el conductor."""
    logger.info(f"Estableciendo vehículo activo {vehicle_id} para conductor: {driver_id}")
    try:
        result = await asyncio.to_thread(
            crud_vehicle.set_active_vehicle_for_driver,
            db,
            vehicle_id=vehicle_id,
            driver_id=driver_id,
        )
        return result
    except Exception as e:
        logger.error(f"Error estableciendo vehículo activo {vehicle_id}: {e}", exc_info=True)
        raise
