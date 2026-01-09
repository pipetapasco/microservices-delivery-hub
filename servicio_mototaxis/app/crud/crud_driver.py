import uuid
from typing import Any

from sqlalchemy.orm import Session

from ..core.logger import get_logger
from ..db.models_db import ESTADOS_DISPONIBILIDAD_VALIDOS, ConductorDB
from ..models.driver_models import DriverCreateRequest

logger = get_logger("crud_driver")


def create_driver(
    db: Session, *, driver_in: DriverCreateRequest, hashed_password: str
) -> ConductorDB:
    """Crea un nuevo conductor en la base de datos."""
    logger.info(f"Creando conductor con email: {driver_in.email}")
    db_driver = ConductorDB(
        email=driver_in.email,
        nombre_completo=driver_in.nombre_completo,
        telefono=driver_in.telefono,
        hash_contrasena=hashed_password,
        tipo_documento=driver_in.tipo_documento,
        numero_documento=driver_in.numero_documento,
        direccion_residencia=driver_in.direccion_residencia,
        ciudad_residencia=driver_in.ciudad_residencia,
    )
    db.add(db_driver)
    try:
        db.commit()
        db.refresh(db_driver)
        logger.info(f"Conductor creado con ID: {db_driver.id_conductor}")
        return db_driver
    except Exception as e:
        db.rollback()
        logger.error(f"Error al crear conductor: {e}", exc_info=True)
        raise


def get_driver_by_email(db: Session, email: str) -> ConductorDB | None:
    """Obtiene un conductor por su email."""
    return db.query(ConductorDB).filter(ConductorDB.email == email).first()


def get_driver_by_id(db: Session, driver_id: uuid.UUID) -> ConductorDB | None:
    """Obtiene un conductor por su ID."""
    return db.query(ConductorDB).filter(ConductorDB.id_conductor == driver_id).first()


def update_driver_profile(
    db: Session, driver_id: uuid.UUID, profile_data_in: dict[str, Any]
) -> ConductorDB | None:
    """Actualiza el perfil de un conductor."""
    db_driver = get_driver_by_id(db, driver_id=driver_id)
    if not db_driver:
        return None
    for field, value in profile_data_in.items():
        if hasattr(db_driver, field) and value is not None:
            setattr(db_driver, field, value)
    try:
        db.add(db_driver)
        db.commit()
        db.refresh(db_driver)
        return db_driver
    except Exception as e:
        db.rollback()
        logger.error(f"Error actualizando perfil: {e}", exc_info=True)
        raise


def update_driver_password_hash(
    db: Session, driver_id: uuid.UUID, new_hashed_password: str
) -> ConductorDB | None:
    """Actualiza la contraseña de un conductor."""
    db_driver = get_driver_by_id(db, driver_id=driver_id)
    if not db_driver:
        return None
    db_driver.hash_contrasena = new_hashed_password
    try:
        db.add(db_driver)
        db.commit()
        db.refresh(db_driver)
        return db_driver
    except Exception as e:
        db.rollback()
        logger.error(f"Error actualizando contraseña: {e}", exc_info=True)
        raise


def update_driver_availability_status(
    db: Session, driver_id: uuid.UUID, nuevo_estado: str
) -> ConductorDB | None:
    """Actualiza el estado de disponibilidad de un conductor."""
    if nuevo_estado not in ESTADOS_DISPONIBILIDAD_VALIDOS:
        logger.warning(f"Estado de disponibilidad inválido: {nuevo_estado}")
        return None
    db_driver = get_driver_by_id(db, driver_id=driver_id)
    if not db_driver:
        return None
    db_driver.estado_disponibilidad = nuevo_estado
    try:
        db.add(db_driver)
        db.commit()
        db.refresh(db_driver)
        return db_driver
    except Exception as e:
        db.rollback()
        logger.error(f"Error actualizando estado: {e}", exc_info=True)
        raise


def get_available_validated_drivers(
    db: Session, skip: int = 0, limit: int = 1000
) -> list[ConductorDB]:
    """Obtiene conductores disponibles y validados."""
    logger.info("Buscando conductores disponibles y validados...")
    return (
        db.query(ConductorDB)
        .filter(
            ConductorDB.activo,
            ConductorDB.estado_validacion_general == "aprobado",
            ConductorDB.estado_disponibilidad == "disponible",
        )
        .offset(skip)
        .limit(limit)
        .all()
    )


def approve_and_make_available_for_testing(db: Session, driver_id: uuid.UUID) -> ConductorDB | None:
    """Aprueba y habilita un conductor para pruebas."""
    db_driver = get_driver_by_id(db, driver_id=driver_id)
    if not db_driver:
        logger.warning(f"Conductor {driver_id} no encontrado para habilitar")
        return None

    db_driver.estado_validacion_general = "aprobado"
    db_driver.estado_disponibilidad = "disponible"
    db_driver.activo = True

    try:
        db.add(db_driver)
        db.commit()
        db.refresh(db_driver)
        logger.info(f"Conductor {driver_id} habilitado para pruebas")
        return db_driver
    except Exception as e:
        db.rollback()
        logger.error(f"Error habilitando conductor {driver_id}: {e}", exc_info=True)
        raise
