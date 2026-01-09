import uuid
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from ..core.logger import get_logger
from ..db.models_db import HistorialServicioDB
from ..models.service_models import POSIBLES_ESTADOS_SERVICIO, ServiceCreateForDriver

logger = get_logger("crud_service_history")


def create_service_entry(db: Session, *, service_in: ServiceCreateForDriver) -> HistorialServicioDB:
    """
    Crea un nuevo registro de servicio para un conductor.
    Esto es una simulación, ya que la creación de servicios vendría de otro microservicio (pedidos).
    """
    logger.info(f"Creando entrada de servicio para conductor ID: {service_in.id_conductor}")

    db_service = HistorialServicioDB(
        id_conductor=service_in.id_conductor,
        id_vehiculo_usado=service_in.id_vehiculo_usado,
        id_cliente=service_in.id_cliente,
        tipo_servicio_realizado=service_in.tipo_servicio_realizado,
        origen_descripcion=service_in.origen_descripcion,
        origen_latitud=service_in.origen_latitud,
        origen_longitud=service_in.origen_longitud,
        destino_descripcion=service_in.destino_descripcion,
        destino_latitud=service_in.destino_latitud,
        destino_longitud=service_in.destino_longitud,
        estado_servicio=service_in.estado_servicio or "solicitado",
        fecha_hora_solicitud=datetime.now(UTC),
    )
    db.add(db_service)
    try:
        db.commit()
        db.refresh(db_service)
        logger.info(f"Servicio creado con ID: {db_service.id_servicio}")
        return db_service
    except Exception as e:
        db.rollback()
        logger.error(f"Error al crear servicio: {e}", exc_info=True)
        raise


def get_services_by_driver_id(
    db: Session,
    *,
    driver_id: uuid.UUID,
    service_status_filter: list[str] | None = None,
    active_services: bool = False,
    history_services: bool = False,
    skip: int = 0,
    limit: int = 100,
) -> list[HistorialServicioDB]:
    """
    Obtiene los servicios de un conductor, con opción de filtrar por estado.
    """
    query = db.query(HistorialServicioDB).filter(HistorialServicioDB.id_conductor == driver_id)

    if service_status_filter:
        query = query.filter(HistorialServicioDB.estado_servicio.in_(service_status_filter))
    elif active_services:
        active_statuses = [
            "aceptado",
            "en_camino_origen",
            "en_origen",
            "viaje_iniciado",
            "en_destino",
        ]
        query = query.filter(HistorialServicioDB.estado_servicio.in_(active_statuses))
    elif history_services:
        history_statuses = [
            "completado",
            "cancelado_conductor",
            "cancelado_cliente",
            "problema_reportado",
        ]
        query = query.filter(HistorialServicioDB.estado_servicio.in_(history_statuses))

    query = query.order_by(HistorialServicioDB.fecha_hora_solicitud.desc())
    return query.offset(skip).limit(limit).all()


def get_service_by_id_and_driver_id(
    db: Session, *, service_id: uuid.UUID, driver_id: uuid.UUID
) -> HistorialServicioDB | None:
    """Obtiene un servicio específico que pertenece a un conductor."""
    return (
        db.query(HistorialServicioDB)
        .filter(
            HistorialServicioDB.id_servicio == service_id,
            HistorialServicioDB.id_conductor == driver_id,
        )
        .first()
    )


def update_service_status(
    db: Session, *, db_service: HistorialServicioDB, nuevo_estado: str
) -> HistorialServicioDB | None:
    """Actualiza el estado de un servicio existente."""
    if nuevo_estado not in POSIBLES_ESTADOS_SERVICIO:
        logger.warning(f"Estado '{nuevo_estado}' no es válido para actualización")
        return None

    logger.info(f"Actualizando estado del servicio ID: {db_service.id_servicio} a '{nuevo_estado}'")
    db_service.estado_servicio = nuevo_estado

    if nuevo_estado == "viaje_iniciado" and not db_service.fecha_hora_inicio_viaje:
        db_service.fecha_hora_inicio_viaje = datetime.now(UTC)
    elif (
        nuevo_estado in ["completado", "cancelado_conductor", "cancelado_cliente"]
        and not db_service.fecha_hora_fin_viaje
    ):
        db_service.fecha_hora_fin_viaje = datetime.now(UTC)
        if not db_service.fecha_hora_inicio_viaje:
            db_service.fecha_hora_inicio_viaje = db_service.fecha_hora_fin_viaje

    db.add(db_service)
    try:
        db.commit()
        db.refresh(db_service)
        return db_service
    except Exception as e:
        db.rollback()
        logger.error(f"Error al actualizar estado del servicio: {e}", exc_info=True)
        raise
