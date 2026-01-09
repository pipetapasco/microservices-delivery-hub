import uuid

from sqlalchemy.orm import Session

from ..core.logger import get_logger
from ..db.models_db import VehiculoConductorDB
from ..models.driver_models import VehicleCreate, VehicleUpdate

logger = get_logger("crud_vehicle")


def create_driver_vehicle(
    db: Session, *, vehicle_in: VehicleCreate, driver_id: uuid.UUID
) -> VehiculoConductorDB:
    """Crea un nuevo vehículo para un conductor."""
    logger.info(f"Creando vehículo para conductor {driver_id} con placa: {vehicle_in.placa}")
    db_vehicle = VehiculoConductorDB(id_conductor=driver_id, **vehicle_in.model_dump())
    db.add(db_vehicle)
    try:
        db.commit()
        db.refresh(db_vehicle)
        logger.info(f"Vehículo creado con ID: {db_vehicle.id_vehiculo}")
        return db_vehicle
    except Exception as e:
        db.rollback()
        logger.error(f"Error al crear vehículo: {e}", exc_info=True)
        raise


def get_driver_vehicles(
    db: Session, *, driver_id: uuid.UUID, skip: int = 0, limit: int = 100
) -> list[VehiculoConductorDB]:
    """Obtiene todos los vehículos de un conductor."""
    return (
        db.query(VehiculoConductorDB)
        .filter(VehiculoConductorDB.id_conductor == driver_id)
        .offset(skip)
        .limit(limit)
        .all()
    )


def get_driver_vehicle_by_id(
    db: Session, *, vehicle_id: uuid.UUID, driver_id: uuid.UUID
) -> VehiculoConductorDB | None:
    """Obtiene un vehículo específico de un conductor."""
    return (
        db.query(VehiculoConductorDB)
        .filter(
            VehiculoConductorDB.id_vehiculo == vehicle_id,
            VehiculoConductorDB.id_conductor == driver_id,
        )
        .first()
    )


def update_driver_vehicle(
    db: Session, *, db_vehicle_obj: VehiculoConductorDB, vehicle_in: VehicleUpdate
) -> VehiculoConductorDB:
    """Actualiza un vehículo existente."""
    update_data = vehicle_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_vehicle_obj, field, value)

    db.add(db_vehicle_obj)
    try:
        db.commit()
        db.refresh(db_vehicle_obj)
        return db_vehicle_obj
    except Exception as e:
        db.rollback()
        logger.error(f"Error al actualizar vehículo: {e}", exc_info=True)
        raise


def delete_driver_vehicle(db: Session, *, vehicle_id: uuid.UUID, driver_id: uuid.UUID) -> bool:
    """Elimina un vehículo de un conductor."""
    db_vehicle = get_driver_vehicle_by_id(db, vehicle_id=vehicle_id, driver_id=driver_id)
    if db_vehicle:
        logger.info(f"Eliminando vehículo {vehicle_id} del conductor {driver_id}")
        db.delete(db_vehicle)
        try:
            db.commit()
            return True
        except Exception as e:
            db.rollback()
            logger.error(f"Error al eliminar vehículo: {e}", exc_info=True)
            raise
    return False


def set_active_vehicle_for_driver(
    db: Session, *, vehicle_id: uuid.UUID, driver_id: uuid.UUID
) -> VehiculoConductorDB | None:
    """Marca un vehículo como activo y desactiva los demás."""
    logger.info(f"Activando vehículo {vehicle_id} para conductor {driver_id}")

    db.query(VehiculoConductorDB).filter(VehiculoConductorDB.id_conductor == driver_id).update(
        {"activo": False}
    )

    vehicle_to_activate = (
        db.query(VehiculoConductorDB)
        .filter(
            VehiculoConductorDB.id_vehiculo == vehicle_id,
            VehiculoConductorDB.id_conductor == driver_id,
        )
        .first()
    )

    if vehicle_to_activate:
        vehicle_to_activate.activo = True
        db.add(vehicle_to_activate)
        try:
            db.commit()
            db.refresh(vehicle_to_activate)
            logger.info(f"Vehículo {vehicle_id} activado")
            return vehicle_to_activate
        except Exception as e:
            db.rollback()
            logger.error(f"Error al activar vehículo: {e}", exc_info=True)
            raise
    else:
        db.rollback()
        logger.warning(f"Vehículo {vehicle_id} no encontrado para activar")
        return None
