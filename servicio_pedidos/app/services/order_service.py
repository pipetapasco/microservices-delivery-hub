# servicio_pedidos/app/services/order_service.py
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import settings
from ..core.logging_config import get_logger
from ..crud import crud_order
from ..db.models_db import PedidoDB
from ..models.order_models import ESTADOS_PEDIDO_VALIDOS, OrderCreateRequest, OrderUpdateRequest
from . import rabbitmq_producer_service

logger = get_logger(__name__)

TRANSICIONES_ESTADO_PERMITIDAS = {
    "solicitado": ["confirmado", "cancelado_usuario", "cancelado_sistema"],
    "confirmado": [
        "buscando_conductor",
        "asignado_conductor",
        "en_proceso_empresa",
        "listo_para_recoger",
        "cancelado_sistema",
        "cancelado_usuario",
    ],
    "buscando_conductor": ["asignado_conductor", "cancelado_sistema", "confirmado"],
    "asignado_conductor": [
        "en_camino_origen",
        "cancelado_conductor",
        "cancelado_sistema",
        "cancelado_usuario",
    ],
    "en_proceso_empresa": ["listo_para_recoger", "cancelado_sistema"],
    "listo_para_recoger": ["asignado_conductor", "buscando_conductor", "cancelado_sistema"],
    "en_camino_origen": ["en_origen", "cancelado_conductor"],
    "en_origen": ["viaje_iniciado", "cancelado_conductor"],
    "viaje_iniciado": ["en_destino", "problema_reportado", "cancelado_conductor"],
    "en_destino": ["entregado", "completado", "problema_reportado"],
    "entregado": ["completado"],
    "completado": [],
    "cancelado_usuario": [],
    "cancelado_sistema": [],
    "cancelado_conductor": [],
    "problema_reportado": ["completado", "cancelado_sistema"],
}


async def create_new_order(db: AsyncSession, *, order_in: OrderCreateRequest) -> PedidoDB | None:
    """Creates a new order and publishes dispatch event."""
    logger.info(
        f"Creating new order for client: {order_in.nombre_cliente or order_in.id_cliente_externo}, Type: {order_in.tipo_servicio}"
    )

    if (
        order_in.tipo_servicio in ["compras", "domicilio"]
        and not order_in.id_empresa_asociada
        and not order_in.items_pedido
    ):
        logger.warning(f"Order of type '{order_in.tipo_servicio}' without company or items.")

    # Direct async call - no asyncio.to_thread needed
    db_order = await crud_order.create_order(db=db, order_in=order_in)

    if db_order:
        logger.info(
            f"Order created in DB with ID: {db_order.id_pedido}, Status: {db_order.estado_pedido}"
        )

        if db_order.estado_pedido == "solicitado":
            order_update_payload = OrderUpdateRequest(estado_pedido="confirmado")
            db_order_confirmado = await crud_order.update_order(
                db=db, db_order=db_order, order_in=order_update_payload
            )

            if db_order_confirmado and db_order_confirmado.estado_pedido == "confirmado":
                logger.info(f"Order ID: {db_order_confirmado.id_pedido} confirmed")

                evento_despacho = {
                    "id_pedido": str(db_order_confirmado.id_pedido),
                    "tipo_servicio": db_order_confirmado.tipo_servicio,
                    "origen_descripcion": db_order_confirmado.origen_descripcion,
                    "origen_latitud": (
                        float(db_order_confirmado.origen_latitud)
                        if db_order_confirmado.origen_latitud
                        else None
                    ),
                    "origen_longitud": (
                        float(db_order_confirmado.origen_longitud)
                        if db_order_confirmado.origen_longitud
                        else None
                    ),
                    "destino_descripcion": db_order_confirmado.destino_descripcion,
                    "destino_latitud": (
                        float(db_order_confirmado.destino_latitud)
                        if db_order_confirmado.destino_latitud
                        else None
                    ),
                    "destino_longitud": (
                        float(db_order_confirmado.destino_longitud)
                        if db_order_confirmado.destino_longitud
                        else None
                    ),
                    "nombre_cliente": db_order_confirmado.nombre_cliente,
                    "telefono_cliente": db_order_confirmado.telefono_cliente,
                    "id_empresa_asociada": db_order_confirmado.id_empresa_asociada,
                    "items_pedido": (
                        [item.model_dump() for item in order_in.items_pedido]
                        if order_in.items_pedido
                        else []
                    ),
                    "detalles_adicionales_pedido": db_order_confirmado.detalles_adicionales_pedido,
                    "metodo_pago_sugerido": db_order_confirmado.metodo_pago_sugerido,
                    "monto_estimado_pedido": (
                        float(db_order_confirmado.monto_estimado_pedido)
                        if db_order_confirmado.monto_estimado_pedido
                        else None
                    ),
                    "fecha_solicitud_utc": db_order_confirmado.fecha_creacion_pedido.isoformat(),
                }

                logger.info(
                    f"Publishing dispatch event for order ID: {db_order_confirmado.id_pedido}"
                )
                await rabbitmq_producer_service.publicar_evento_pedido_para_despacho(
                    tipo_despacho_key=settings.RABBITMQ_DISPATCH_MOTOTAXI_ROUTING_KEY,
                    datos_pedido_evento=evento_despacho,
                )

                return db_order_confirmado
            else:
                logger.warning(
                    f"Order ID: {db_order.id_pedido} created but could not be confirmed."
                )
                return db_order
        return db_order
    return None


async def get_order_details(db: AsyncSession, order_id: uuid.UUID) -> PedidoDB | None:
    """Gets order details by ID."""
    return await crud_order.get_order_by_id(db=db, order_id=order_id)


async def get_orders_list_by_status(
    db: AsyncSession, status: str, skip: int = 0, limit: int = 100
) -> list[PedidoDB]:
    """Gets orders filtered by status."""
    if status not in ESTADOS_PEDIDO_VALIDOS:
        return []
    return await crud_order.get_orders_by_status(db=db, status=status, skip=skip, limit=limit)


async def get_orders_list_by_driver(
    db: AsyncSession, driver_id: uuid.UUID, skip: int = 0, limit: int = 100
) -> list[PedidoDB]:
    """Gets orders assigned to a driver."""
    return await crud_order.get_orders_by_driver_id(
        db=db, driver_id=driver_id, skip=skip, limit=limit
    )


async def update_order_by_id(
    db: AsyncSession,
    order_id: uuid.UUID,
    order_update_in: OrderUpdateRequest,
    actor_tipo: str,
    actor_id: str,
) -> PedidoDB | None:
    """Updates an order with state transition validation."""
    db_order = await get_order_details(db, order_id)
    if not db_order:
        return None

    nuevo_estado_solicitado = order_update_in.estado_pedido
    estado_actual = db_order.estado_pedido

    if nuevo_estado_solicitado and nuevo_estado_solicitado != estado_actual:
        logger.info(
            f"Order ID {db_order.id_pedido}, state change from '{estado_actual}' to '{nuevo_estado_solicitado}' by {actor_tipo}:{actor_id}"
        )
        permitidos = TRANSICIONES_ESTADO_PERMITIDAS.get(estado_actual, [])
        if nuevo_estado_solicitado not in permitidos:
            logger.error(
                f"State transition from '{estado_actual}' to '{nuevo_estado_solicitado}' not allowed."
            )
            return None

    updated_db_order = await crud_order.update_order(
        db=db, db_order=db_order, order_in=order_update_in
    )
    logger.info(
        f"Order ID: {updated_db_order.id_pedido} updated to status '{updated_db_order.estado_pedido}'."
    )

    if (
        updated_db_order.estado_pedido == "asignado_conductor"
        and updated_db_order.id_conductor_asignado
    ):
        logger.info(
            f"Driver {updated_db_order.id_conductor_asignado} assigned to order {updated_db_order.id_pedido}"
        )

    return updated_db_order
