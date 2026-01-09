import asyncio
import uuid
from datetime import UTC, datetime, timedelta

from jose import jwt
from passlib.context import CryptContext
from pydantic import EmailStr
from sqlalchemy.orm import Session

from ..core.config import settings
from ..core.logger import get_logger
from ..crud import crud_driver
from ..db.models_db import ConductorDB
from ..models.driver_models import (
    DriverChangePasswordRequest,
    DriverCreateRequest,
    DriverProfileUpdate,
    DriverStatusUpdate,
)

logger = get_logger("auth_service")
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(UTC) + expires_delta
    else:
        expire = datetime.now(UTC) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(
        to_encode, settings.JWT_SECRET_KEY_MOTOTAXIS, algorithm=settings.JWT_ALGORITHM
    )


async def registrar_nuevo_conductor(
    db: Session, *, driver_data: DriverCreateRequest
) -> ConductorDB | None:
    """Registra un nuevo conductor en el sistema."""
    db_driver_by_email = await asyncio.to_thread(
        crud_driver.get_driver_by_email, db, email=driver_data.email
    )
    if db_driver_by_email:
        logger.warning(f"Intento de registro con email duplicado: {driver_data.email}")
        return None

    hashed_password = await asyncio.to_thread(get_password_hash, driver_data.password)
    try:
        new_driver = await asyncio.to_thread(
            crud_driver.create_driver, db, driver_in=driver_data, hashed_password=hashed_password
        )
        logger.info(f"Nuevo conductor registrado: {new_driver.id_conductor}")
        return new_driver
    except Exception as e:
        logger.error(f"Error al registrar conductor: {e}", exc_info=True)
        raise


async def autenticar_conductor(
    db: Session, *, email: EmailStr, password: str
) -> ConductorDB | None:
    """Autentica un conductor por email y contraseña."""
    conductor_en_db = await asyncio.to_thread(crud_driver.get_driver_by_email, db, email=email)
    if not conductor_en_db:
        logger.warning(f"Intento de autenticación con email inexistente: {email}")
        return None
    if not await asyncio.to_thread(verify_password, password, conductor_en_db.hash_contrasena):
        logger.warning(f"Contraseña incorrecta para: {email}")
        return None
    return conductor_en_db


async def get_driver_by_id_service(db: Session, driver_id: uuid.UUID) -> ConductorDB | None:
    """Obtiene un conductor por su ID."""
    return await asyncio.to_thread(crud_driver.get_driver_by_id, db, driver_id=driver_id)


async def actualizar_perfil_conductor_service(
    db: Session, driver_id: uuid.UUID, profile_update_data: DriverProfileUpdate
) -> ConductorDB | None:
    """Actualiza el perfil de un conductor."""
    update_data_dict = profile_update_data.model_dump(exclude_unset=True)
    if not update_data_dict:
        return await get_driver_by_id_service(db, driver_id)

    try:
        updated_driver = await asyncio.to_thread(
            crud_driver.update_driver_profile,
            db,
            driver_id=driver_id,
            profile_data_in=update_data_dict,
        )
        if updated_driver:
            logger.info(f"Perfil actualizado para conductor: {driver_id}")
        return updated_driver
    except Exception as e:
        logger.error(f"Error actualizando perfil del conductor {driver_id}: {e}", exc_info=True)
        raise


async def cambiar_contrasena_conductor_service(
    db: Session, driver_id: uuid.UUID, password_data: DriverChangePasswordRequest
) -> tuple[bool, str]:
    """Cambia la contraseña de un conductor."""
    conductor_actual = await get_driver_by_id_service(db, driver_id)
    if not conductor_actual:
        return False, "Conductor no encontrado."

    if not await asyncio.to_thread(
        verify_password, password_data.current_password, conductor_actual.hash_contrasena
    ):
        logger.warning(f"Intento de cambio de contraseña fallido para: {driver_id}")
        return False, "La contraseña actual es incorrecta."

    nuevo_hash_contrasena = await asyncio.to_thread(get_password_hash, password_data.new_password)
    try:
        conductor_actualizado = await asyncio.to_thread(
            crud_driver.update_driver_password_hash,
            db,
            driver_id=driver_id,
            new_hashed_password=nuevo_hash_contrasena,
        )
        if conductor_actualizado:
            logger.info(f"Contraseña cambiada para conductor: {driver_id}")
            return True, "Contraseña cambiada exitosamente."
        return False, "Error al actualizar la contraseña en la DB."
    except Exception as e:
        logger.error(f"Error cambiando contraseña del conductor {driver_id}: {e}", exc_info=True)
        raise


async def cambiar_estado_disponibilidad_conductor_service(
    db: Session, driver_id: uuid.UUID, status_update_data: DriverStatusUpdate
) -> ConductorDB | None:
    """Cambia el estado de disponibilidad de un conductor."""
    try:
        conductor_actualizado = await asyncio.to_thread(
            crud_driver.update_driver_availability_status,
            db,
            driver_id=driver_id,
            nuevo_estado=status_update_data.estado_disponibilidad,
        )
        if conductor_actualizado:
            logger.info(
                f"Estado de disponibilidad actualizado a '{status_update_data.estado_disponibilidad}' para: {driver_id}"
            )
        return conductor_actualizado
    except Exception as e:
        logger.error(
            f"Error cambiando estado de disponibilidad para {driver_id}: {e}", exc_info=True
        )
        raise


async def habilitar_conductor_para_pruebas_service(
    db: Session, driver_id: uuid.UUID
) -> ConductorDB | None:
    """Habilita un conductor para pruebas (desarrollo)."""
    logger.info(f"Habilitando conductor {driver_id} para pruebas...")
    try:
        conductor_habilitado = await asyncio.to_thread(
            crud_driver.approve_and_make_available_for_testing, db, driver_id=driver_id
        )
        if conductor_habilitado:
            logger.info(f"Conductor {driver_id} habilitado exitosamente para pruebas")
        else:
            logger.warning(
                f"No se pudo habilitar conductor {driver_id} (posiblemente no encontrado)"
            )
        return conductor_habilitado
    except Exception as e:
        logger.error(f"Error habilitando conductor {driver_id} para pruebas: {e}", exc_info=True)
        raise
