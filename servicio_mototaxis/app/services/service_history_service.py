import asyncio
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from ..core.config import settings
from ..core.logger import get_logger
from ..crud import crud_driver, crud_service_history
from ..db.models_db import ConductorDB, HistorialServicioDB
from ..models.service_models import ServiceStatusUpdateRequest
from . import rabbitmq_producer_service as mototaxi_rabbitmq_producer

logger = get_logger("service_history_service")


async def list_driver_service_history(
    db: Session, *, driver_id: uuid.UUID, skip: int = 0, limit: int = 100
) -> list[HistorialServicioDB]:
    """Lista el historial de servicios de un conductor."""
    return await asyncio.to_thread(
        crud_service_history.get_services_by_driver_id,
        db,
        driver_id=driver_id,
        history_services=True,
        skip=skip,
        limit=limit,
    )


async def list_driver_active_services(
    db: Session, *, driver_id: uuid.UUID, skip: int = 0, limit: int = 100
) -> list[HistorialServicioDB]:
    """Lista los servicios activos de un conductor."""
    return await asyncio.to_thread(
        crud_service_history.get_services_by_driver_id,
        db,
        driver_id=driver_id,
        active_services=True,
        skip=skip,
        limit=limit,
    )


async def update_driver_service_status(
    db: Session,
    *,
    driver_id: uuid.UUID,
    service_id: uuid.UUID,
    status_update_in: ServiceStatusUpdateRequest,
) -> HistorialServicioDB | None:
    """Actualiza el estado de un servicio."""
    db_service = await asyncio.to_thread(
        crud_service_history.get_service_by_id_and_driver_id,
        db,
        service_id=service_id,
        driver_id=driver_id,
    )
    if not db_service:
        return None

    updated_service = await asyncio.to_thread(
        crud_service_history.update_service_status,
        db,
        db_service=db_service,
        nuevo_estado=status_update_in.nuevo_estado,
    )

    if updated_service:
        evento_actualizacion = {
            "id_pedido": str(updated_service.id_servicio),
            "id_conductor": str(driver_id),
            "nuevo_estado_conductor": updated_service.estado_servicio,
            "timestamp_actualizacion_conductor": datetime.now(UTC).isoformat(),
        }
        await mototaxi_rabbitmq_producer.publicar_evento_actualizacion_pedido(
            routing_key=settings.RABBITMQ_ORDER_UPDATE_ROUTING_KEY,
            datos_evento=evento_actualizacion,
        )
    return updated_service


async def accept_service_by_driver(
    db: Session, *, driver_id: uuid.UUID, service_id_from_pedidos: uuid.UUID
) -> tuple[bool, str, dict[str, Any] | None]:
    """Permite al conductor aceptar un servicio."""
    logger.info(f"Conductor {driver_id} intentando aceptar servicio: {service_id_from_pedidos}")

    try:
        conductor: ConductorDB | None = await asyncio.to_thread(
            crud_driver.get_driver_by_id, db, driver_id=driver_id
        )
        if not conductor:
            return False, "Conductor no encontrado.", None
        if not conductor.activo or conductor.estado_validacion_general != "aprobado":
            return False, "Tu cuenta no está activa o validada para tomar servicios.", None
        if conductor.estado_disponibilidad != "disponible":
            return (
                False,
                f"No puedes aceptar servicios. Tu estado actual es '{conductor.estado_disponibilidad}'.",
                None,
            )

        logger.info(f"Conductor {driver_id} validado y disponible")

        conductor_actualizado = await asyncio.to_thread(
            crud_driver.update_driver_availability_status,
            db,
            driver_id=driver_id,
            nuevo_estado="en_servicio",
        )
        if not conductor_actualizado:
            logger.error(f"No se pudo actualizar estado del conductor {driver_id} a 'en_servicio'")
            return False, "Error interno al actualizar tu estado. Intenta de nuevo.", None

        logger.info(f"Estado del conductor {driver_id} actualizado a 'en_servicio'")

        placa_activa = None
        if conductor.vehiculos:
            for vehiculo_obj in conductor.vehiculos:
                if (
                    hasattr(vehiculo_obj, "activo")
                    and vehiculo_obj.activo
                    and hasattr(vehiculo_obj, "placa")
                ):
                    placa_activa = vehiculo_obj.placa
                    break
        if not placa_activa:
            logger.warning(f"Conductor {driver_id} no tiene un vehículo activo con placa")

        evento_aceptacion = {
            "id_pedido": str(service_id_from_pedidos),
            "id_conductor_que_acepto": str(driver_id),
            "nombre_conductor": conductor.nombre_completo,
            "placa_vehiculo_activa": placa_activa,
            "timestamp_aceptacion_utc": datetime.now(UTC).isoformat(),
            "nuevo_estado_para_pedido": "asignado_conductor",
        }

        publicado_exitosamente = (
            await mototaxi_rabbitmq_producer.publicar_evento_actualizacion_pedido(
                routing_key=settings.RABBITMQ_ORDER_UPDATE_ROUTING_KEY,
                datos_evento=evento_aceptacion,
            )
        )

        if publicado_exitosamente:
            mensaje_exito = (
                f"Servicio {service_id_from_pedidos} aceptado. Notificando al sistema de pedidos."
            )
            logger.info(mensaje_exito)
            return (
                True,
                mensaje_exito,
                {
                    "id_pedido_aceptado": str(service_id_from_pedidos),
                    "id_conductor": str(driver_id),
                },
            )
        else:
            logger.error(
                f"Falló la publicación a RabbitMQ. Revirtiendo estado del conductor {driver_id}"
            )
            conductor_revertido = await asyncio.to_thread(
                crud_driver.update_driver_availability_status,
                db,
                driver_id=driver_id,
                nuevo_estado="disponible",
            )
            await asyncio.to_thread(db.commit)

            if conductor_revertido:
                logger.info(f"Estado del conductor {driver_id} revertido a 'disponible'")
            else:
                logger.error(
                    f"ERROR CRÍTICO: No se pudo revertir el estado del conductor {driver_id}"
                )

            return (
                False,
                "Servicio aceptado, pero hubo un error notificando al sistema de pedidos. Tu estado ha sido revertido. Intenta de nuevo.",
                None,
            )

    except Exception:
        logger.exception(
            f"Excepción no controlada en accept_service_by_driver para conductor {driver_id}"
        )
        return False, "Error interno del servidor al intentar aceptar el servicio.", None
