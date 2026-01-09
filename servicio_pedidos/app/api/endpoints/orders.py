# servicio_pedidos/app/api/endpoints/orders.py
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.logging_config import get_logger
from ...core.security import verify_token
from ...db.session import get_db
from ...models.order_models import OrderCreateRequest, OrderResponse, OrderUpdateRequest
from ...services import order_service

logger = get_logger(__name__)

router = APIRouter()


@router.post(
    "/",
    response_model=OrderResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear un nuevo pedido",
)
async def create_new_order_endpoint(
    *,
    db: AsyncSession = Depends(get_db),
    order_in: OrderCreateRequest,
    current_user: dict = Depends(verify_token),  # Protected endpoint
):
    """
    Crea un nuevo pedido con sus ítems.
    Requiere autenticación.
    """
    logger.info(f"User {current_user.get('user_id')} creating order: {order_in.tipo_servicio}")

    db_order = await order_service.create_new_order(db=db, order_in=order_in)
    if not db_order:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se pudo crear el pedido. Verifique los datos.",
        )
    return OrderResponse.model_validate(db_order)


@router.get(
    "/{order_id_str}", response_model=OrderResponse, summary="Obtener detalles de un pedido"
)
async def get_order_details_endpoint(
    order_id_str: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(verify_token),  # Protected endpoint
):
    """Obtiene los detalles de un pedido por ID. Requiere autenticación."""
    try:
        order_id_uuid = uuid.UUID(order_id_str)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"ID '{order_id_str}' no es un UUID válido.",
        )

    logger.debug(f"User {current_user.get('user_id')} requesting order: {order_id_uuid}")
    db_order = await order_service.get_order_details(db=db, order_id=order_id_uuid)

    if not db_order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Pedido '{order_id_uuid}' no encontrado."
        )
    return OrderResponse.model_validate(db_order)


@router.get(
    "/status/{status_value}",
    response_model=list[OrderResponse],
    summary="Listar pedidos por estado",
)
async def list_orders_by_status_endpoint(
    status_value: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(verify_token),  # Protected endpoint
    skip: int = 0,
    limit: int = 50,
):
    """Obtiene pedidos filtrados por estado. Requiere autenticación."""
    logger.debug(f"User {current_user.get('user_id')} listing orders with status: {status_value}")

    orders = await order_service.get_orders_list_by_status(
        db=db, status=status_value, skip=skip, limit=limit
    )

    if not orders and status_value not in order_service.ESTADOS_PEDIDO_VALIDOS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"Estado '{status_value}' no es válido."
        )
    return [OrderResponse.model_validate(order) for order in orders]


@router.get(
    "/driver/{driver_id_str}",
    response_model=list[OrderResponse],
    summary="Listar pedidos de un conductor",
)
async def list_orders_by_driver_endpoint(
    driver_id_str: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(verify_token),  # Protected endpoint
    skip: int = 0,
    limit: int = 50,
):
    """Obtiene pedidos asignados a un conductor. Requiere autenticación."""
    try:
        driver_id_uuid = uuid.UUID(driver_id_str)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"ID '{driver_id_str}' no es un UUID válido.",
        )

    logger.debug(f"User {current_user.get('user_id')} listing orders for driver: {driver_id_uuid}")
    orders = await order_service.get_orders_list_by_driver(
        db=db, driver_id=driver_id_uuid, skip=skip, limit=limit
    )
    return [OrderResponse.model_validate(order) for order in orders]


@router.put("/{order_id_str}", response_model=OrderResponse, summary="Actualizar un pedido")
async def update_order_endpoint(
    order_id_str: str,
    order_in: OrderUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(verify_token),  # Protected endpoint
):
    """Actualiza un pedido existente. Requiere autenticación."""
    try:
        order_id_uuid = uuid.UUID(order_id_str)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"ID '{order_id_str}' no es un UUID válido.",
        )

    logger.info(f"User {current_user.get('user_id')} updating order: {order_id_uuid}")

    updated_order_db = await order_service.update_order_by_id(
        db=db,
        order_id=order_id_uuid,
        order_update_in=order_in,
        actor_tipo="api_user",
        actor_id=current_user.get("user_id", "unknown"),
    )

    if not updated_order_db:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pedido '{order_id_uuid}' no encontrado o actualización no permitida.",
        )

    return OrderResponse.model_validate(updated_order_db)
