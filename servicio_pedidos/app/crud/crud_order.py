# servicio_pedidos/app/crud/crud_order.py
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..core.logging_config import get_logger
from ..db.models_db import ItemPedidoDB, PedidoDB
from ..models.order_models import OrderCreateRequest, OrderUpdateRequest

logger = get_logger(__name__)


async def create_order(db: AsyncSession, *, order_in: OrderCreateRequest) -> PedidoDB:
    """Creates a new order in the database asynchronously."""
    logger.info(
        f"Creating new order for client: {order_in.nombre_cliente or order_in.id_cliente_externo}"
    )

    db_order = PedidoDB(
        id_cliente_externo=order_in.id_cliente_externo,
        nombre_cliente=order_in.nombre_cliente,
        telefono_cliente=order_in.telefono_cliente,
        tipo_servicio=order_in.tipo_servicio,
        origen_descripcion=order_in.origen_descripcion,
        origen_latitud=order_in.origen_latitud,
        origen_longitud=order_in.origen_longitud,
        destino_descripcion=order_in.destino_descripcion,
        destino_latitud=order_in.destino_latitud,
        destino_longitud=order_in.destino_longitud,
        id_empresa_asociada=order_in.id_empresa_asociada,
        detalles_adicionales_pedido=order_in.detalles_adicionales_pedido,
        metodo_pago_sugerido=order_in.metodo_pago_sugerido,
        monto_estimado_pedido=order_in.monto_estimado_pedido,
        estado_pedido="solicitado",
        fecha_creacion_pedido=datetime.now(UTC),
        fecha_ultima_actualizacion=datetime.now(UTC),
    )
    db.add(db_order)

    # Flush to get the order ID before adding items
    await db.flush()

    if order_in.items_pedido:
        for item_in in order_in.items_pedido:
            db_item = ItemPedidoDB(
                id_pedido=db_order.id_pedido,
                id_item_menu_empresa=item_in.id_item_menu_empresa,
                nombre_item=item_in.nombre_item,
                cantidad=item_in.cantidad,
                precio_unitario_registrado=item_in.precio_unitario_registrado,
                notas_item=item_in.notas_item,
            )
            db.add(db_item)

    try:
        await db.commit()
        await db.refresh(db_order)
        logger.info(f"Order created with ID: {db_order.id_pedido}")
        return db_order
    except Exception as e:
        await db.rollback()
        logger.exception(f"Error creating order: {e}")
        raise


async def get_order_by_id(db: AsyncSession, order_id: uuid.UUID) -> PedidoDB | None:
    """Gets an order by its ID asynchronously."""
    logger.debug(f"Looking up order with ID: {order_id}")

    stmt = (
        select(PedidoDB).where(PedidoDB.id_pedido == order_id).options(selectinload(PedidoDB.items))
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def get_orders_by_status(
    db: AsyncSession, status: str, skip: int = 0, limit: int = 100
) -> list[PedidoDB]:
    """Gets a list of orders filtered by status asynchronously."""
    logger.debug(f"Fetching orders with status: {status}")

    stmt = (
        select(PedidoDB)
        .where(PedidoDB.estado_pedido == status)
        .order_by(PedidoDB.fecha_creacion_pedido.desc())
        .offset(skip)
        .limit(limit)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_orders_by_driver_id(
    db: AsyncSession, driver_id: uuid.UUID, skip: int = 0, limit: int = 100
) -> list[PedidoDB]:
    """Gets a list of orders assigned to a specific driver asynchronously."""
    logger.debug(f"Fetching orders for driver ID: {driver_id}")

    stmt = (
        select(PedidoDB)
        .where(PedidoDB.id_conductor_asignado == driver_id)
        .order_by(PedidoDB.fecha_creacion_pedido.desc())
        .offset(skip)
        .limit(limit)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def update_order(
    db: AsyncSession, *, db_order: PedidoDB, order_in: OrderUpdateRequest
) -> PedidoDB:
    """Updates an existing order asynchronously."""
    logger.info(f"Updating order ID: {db_order.id_pedido}")

    update_data = order_in.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        if hasattr(db_order, field):
            setattr(db_order, field, value)
            logger.debug(f"Field '{field}' updated to '{value}'")
        else:
            logger.warning(f"Field '{field}' does not exist on PedidoDB model.")

    db_order.fecha_ultima_actualizacion = datetime.now(UTC)

    try:
        await db.commit()
        await db.refresh(db_order)
        return db_order
    except Exception as e:
        await db.rollback()
        logger.exception(f"Error updating order ID {db_order.id_pedido}: {e}")
        raise
