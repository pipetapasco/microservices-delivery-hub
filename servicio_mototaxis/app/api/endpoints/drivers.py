import asyncio
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ...core.logger import get_logger
from ...crud import crud_driver
from ...db.session import get_db
from ...models.driver_models import (
    Driver,
    DriverChangePasswordRequest,
    DriverInDB,
    DriverProfileUpdate,
    DriverStatusUpdate,
    VehicleCreate,
    VehicleResponse,
)
from ...models.service_models import ServiceResponse, ServiceStatusUpdateRequest
from ...services import auth_service, service_history_service, vehicle_service
from .auth import get_current_driver_from_token

logger = get_logger("drivers_api")
router = APIRouter(
    prefix="/drivers",
    tags=["Drivers - Profile, Vehicles, Status & Services"],
)


@router.get("/hello")
async def hello_drivers():
    return {"mensaje": "¡Hola desde el Servicio de Mototaxistas!"}


@router.get("/me", response_model=Driver)
async def read_current_driver_profile(
    current_driver: DriverInDB = Depends(get_current_driver_from_token),
):
    if not current_driver:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Conductor no autenticado"
        )
    return Driver.model_validate(current_driver)


@router.put("/me/profile", response_model=Driver)
async def update_current_driver_profile_endpoint(
    profile_data_in: DriverProfileUpdate,
    db: Session = Depends(get_db),
    current_driver_from_token: DriverInDB = Depends(get_current_driver_from_token),
):
    try:
        conductor_actualizado_db = await auth_service.actualizar_perfil_conductor_service(
            db=db,
            driver_id=current_driver_from_token.id_conductor,
            profile_update_data=profile_data_in,
        )
        if not conductor_actualizado_db:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="No se pudo actualizar el perfil.",
            )
        return Driver.model_validate(conductor_actualizado_db)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error actualizando perfil: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno al actualizar perfil",
        )


@router.put("/me/change-password", status_code=status.HTTP_200_OK)
async def change_current_driver_password(
    password_data_in: DriverChangePasswordRequest,
    db: Session = Depends(get_db),
    current_driver_from_token: DriverInDB = Depends(get_current_driver_from_token),
):
    try:
        exito, mensaje = await auth_service.cambiar_contrasena_conductor_service(
            db=db, driver_id=current_driver_from_token.id_conductor, password_data=password_data_in
        )
        if not exito:
            if "incorrecta" in mensaje.lower():
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=mensaje)
            else:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=mensaje
                )
        return {"mensaje": mensaje}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error cambiando contraseña: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno al cambiar contraseña",
        )


@router.put("/me/status", response_model=Driver)
async def update_driver_availability_status_endpoint(
    status_in: DriverStatusUpdate,
    db: Session = Depends(get_db),
    current_driver_from_token: DriverInDB = Depends(get_current_driver_from_token),
):
    try:
        conductor_actualizado = await auth_service.cambiar_estado_disponibilidad_conductor_service(
            db=db, driver_id=current_driver_from_token.id_conductor, status_update_data=status_in
        )
        if not conductor_actualizado:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="No se pudo actualizar el estado de disponibilidad.",
            )
        return Driver.model_validate(conductor_actualizado)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error actualizando estado: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error interno"
        )


@router.post("/me/vehicles", response_model=VehicleResponse, status_code=status.HTTP_201_CREATED)
async def create_vehicle_for_current_driver(
    vehicle_in: VehicleCreate,
    db: Session = Depends(get_db),
    current_driver: DriverInDB = Depends(get_current_driver_from_token),
):
    try:
        new_vehicle_db = await vehicle_service.add_new_vehicle(
            db=db, driver_id=current_driver.id_conductor, vehicle_in=vehicle_in
        )
        if not new_vehicle_db:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="No se pudo crear el vehículo."
            )
        return VehicleResponse.model_validate(new_vehicle_db)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creando vehículo: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error interno"
        )


@router.get("/me/services/history", response_model=list[ServiceResponse])
async def get_driver_service_history_endpoint(
    db: Session = Depends(get_db),
    current_driver: DriverInDB = Depends(get_current_driver_from_token),
    skip: int = 0,
    limit: int = 20,
):
    history = await service_history_service.list_driver_service_history(
        db=db, driver_id=current_driver.id_conductor, skip=skip, limit=limit
    )
    return [ServiceResponse.model_validate(s) for s in history]


@router.get("/me/services/active", response_model=list[ServiceResponse])
async def get_driver_active_services_endpoint(
    db: Session = Depends(get_db),
    current_driver: DriverInDB = Depends(get_current_driver_from_token),
    skip: int = 0,
    limit: int = 10,
):
    active_services = await service_history_service.list_driver_active_services(
        db=db, driver_id=current_driver.id_conductor, skip=skip, limit=limit
    )
    return [ServiceResponse.model_validate(s) for s in active_services]


@router.put("/me/services/{service_id_str}/update-status", response_model=ServiceResponse)
async def update_service_status_for_driver_endpoint(
    service_id_str: str,
    status_update_in: ServiceStatusUpdateRequest,
    db: Session = Depends(get_db),
    current_driver: DriverInDB = Depends(get_current_driver_from_token),
):
    try:
        service_id_uuid = uuid.UUID(service_id_str)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="ID de servicio no válido."
        )

    updated_service = await service_history_service.update_driver_service_status(
        db=db,
        driver_id=current_driver.id_conductor,
        service_id=service_id_uuid,
        status_update_in=status_update_in,
    )
    if not updated_service:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No se pudo actualizar el servicio o no fue encontrado.",
        )
    return ServiceResponse.model_validate(updated_service)


@router.post("/me/services/{service_id_from_pedidos_str}/accept", status_code=status.HTTP_200_OK)
async def accept_service_endpoint(
    service_id_from_pedidos_str: str,
    db: Session = Depends(get_db),
    current_driver: DriverInDB = Depends(get_current_driver_from_token),
):
    """Permite al conductor autenticado aceptar un servicio."""
    try:
        service_id_uuid = uuid.UUID(service_id_from_pedidos_str)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El ID de servicio no es un UUID válido.",
        )

    logger.info(f"Conductor {current_driver.id_conductor} aceptando servicio: {service_id_uuid}")

    exito, mensaje, _ = await service_history_service.accept_service_by_driver(
        db=db, driver_id=current_driver.id_conductor, service_id_from_pedidos=service_id_uuid
    )

    if not exito:
        if "no está activa o validada" in mensaje or "estado actual es" in mensaje:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=mensaje)
        elif "Error interno" in mensaje or "notificando al sistema" in mensaje:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=mensaje)
        else:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=mensaje)

    return {"mensaje": mensaje, "id_pedido_aceptado": str(service_id_uuid)}


@router.get("/profile/{driver_id_param_str}", response_model=Driver, deprecated=True)
async def get_driver_profile_by_id(driver_id_param_str: str, db: Session = Depends(get_db)):
    try:
        driver_id_uuid = uuid.UUID(driver_id_param_str)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="ID de conductor no válido."
        )

    conductor_encontrado = await asyncio.to_thread(
        crud_driver.get_driver_by_id, db, driver_id=driver_id_uuid
    )
    if not conductor_encontrado:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Conductor no encontrado."
        )
    return Driver.model_validate(conductor_encontrado)


@router.post("/{driver_id_str}/enable-for-testing", response_model=Driver)
async def enable_driver_for_testing_endpoint(driver_id_str: str, db: Session = Depends(get_db)):
    """Endpoint de desarrollo para habilitar un conductor para pruebas. Solo disponible con DEBUG=True."""
    from ...core.config import settings as app_settings

    if not app_settings.DEBUG:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Endpoint no disponible")

    try:
        driver_id_uuid = uuid.UUID(driver_id_str)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El ID de conductor no es un UUID válido.",
        )

    logger.info(f"[DEBUG] Solicitud para habilitar conductor {driver_id_uuid} para pruebas")

    try:
        conductor_habilitado = await auth_service.habilitar_conductor_para_pruebas_service(
            db=db, driver_id=driver_id_uuid
        )
        if not conductor_habilitado:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="No se pudo habilitar el conductor."
            )
        return Driver.model_validate(conductor_habilitado)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error habilitando conductor: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error interno"
        )
