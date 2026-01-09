# servicio_pedidos/app/models/order_models.py
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

# Posibles tipos de servicio que este servicio de pedidos manejará
TIPOS_DE_SERVICIO_VALIDOS = ["mototaxi", "domicilio", "compras"]

# Posibles estados de un pedido
ESTADOS_PEDIDO_VALIDOS = [
    "solicitado",  # Recibido del bot de WhatsApp, pendiente de procesamiento/asignación
    "confirmado",  # El servicio de pedidos ha validado y aceptado la solicitud
    "buscando_conductor",  # Para servicios de mototaxi o domicilios que requieren conductor
    "asignado_conductor",  # Un conductor ha sido asignado
    "en_proceso_empresa",  # Para pedidos de 'compras' o 'domicilio' a una empresa, la empresa está preparando
    "listo_para_recoger",  # El pedido (compras/comida) está listo para ser recogido por el conductor
    "en_camino_cliente",  # El conductor va hacia el cliente (mototaxi) o hacia el destino (domicilio/compras)
    "entregado",  # El servicio/producto ha sido entregado al cliente
    "completado",  # El pedido se ha finalizado completamente (incluye posible pago, etc.)
    "cancelado_usuario",
    "cancelado_sistema",  # Cancelado por el sistema o un administrador
    "cancelado_conductor",
]


class OrderItemBase(
    BaseModel
):  # Para ítems dentro de un pedido de 'compras' o 'domicilio' de restaurante
    id_item_menu_empresa: str | None = Field(
        None, description="ID del ítem en el sistema de la empresa (si aplica)"
    )
    nombre_item: str = Field(..., description="Nombre del producto o ítem")
    cantidad: int = Field(..., gt=0, description="Cantidad solicitada")
    precio_unitario_registrado: float | None = Field(
        None, description="Precio al momento del pedido (para referencia)"
    )
    # Podrías añadir modificadores seleccionados aquí si es un ítem de menú configurable
    # modificadores_seleccionados: Optional[List[Any]] = None
    notas_item: str | None = Field(None, description="Notas específicas para este ítem")


class OrderBase(BaseModel):
    tipo_servicio: str = Field(..., description="Tipo de servicio: mototaxi, domicilio, compras")

    # Información del cliente (podría venir del bot o de un servicio de usuarios)
    id_cliente_externo: str | None = Field(
        None, description="ID del cliente en el sistema de origen (ej. WhatsApp ID)"
    )
    nombre_cliente: str | None = Field(None, description="Nombre del cliente")
    telefono_cliente: str | None = Field(None, description="Teléfono del cliente")

    # Origen (relevante para mototaxi, domicilios)
    origen_descripcion: str | None = Field(None)
    origen_latitud: float | None = None
    origen_longitud: float | None = None

    # Destino (relevante para todos los tipos)
    destino_descripcion: str = Field(...)
    destino_latitud: float | None = None
    destino_longitud: float | None = None

    # Para pedidos a empresas (compras, domicilios de comida)
    id_empresa_asociada: str | None = Field(
        None, description="ID de la empresa/restaurante si aplica"
    )
    items_pedido: list[OrderItemBase] | None = Field(
        None, description="Lista de ítems para compras o domicilios"
    )

    detalles_adicionales_pedido: str | None = Field(
        None, description="Instrucciones generales o detalles adicionales"
    )
    metodo_pago_sugerido: str | None = Field(None)
    monto_estimado_pedido: float | None = Field(
        None, description="Monto estimado o total del pedido"
    )

    @field_validator("tipo_servicio")
    def validar_tipo_servicio(cls, value):
        if value.lower() not in TIPOS_DE_SERVICIO_VALIDOS:
            raise ValueError(
                f"Tipo de servicio inválido. Debe ser uno de: {', '.join(TIPOS_DE_SERVICIO_VALIDOS)}"
            )
        return value.lower()


class OrderCreateRequest(OrderBase):  # Lo que se recibe para crear un nuevo pedido
    # Podría tener campos adicionales específicos para la creación si es necesario
    pass


class OrderUpdateRequest(BaseModel):  # Para actualizar un pedido existente
    # Solo los campos que se pueden actualizar, todos opcionales
    estado_pedido: str | None = None
    id_conductor_asignado: uuid.UUID | None = None  # UUID del conductor
    # ... otros campos actualizables ...

    @field_validator("estado_pedido")
    def validar_estado_pedido(cls, value):
        if value is not None and value.lower() not in ESTADOS_PEDIDO_VALIDOS:
            raise ValueError(
                f"Estado de pedido inválido. Debe ser uno de: {', '.join(ESTADOS_PEDIDO_VALIDOS)}"
            )
        return value.lower() if value else None


class OrderInDB(OrderBase):
    id_pedido: uuid.UUID = Field(default_factory=uuid.uuid4)
    id_conductor_asignado: uuid.UUID | None = None  # UUID del conductor

    estado_pedido: str = Field(default="solicitado")
    fecha_creacion_pedido: datetime = Field(default_factory=datetime.utcnow)
    fecha_ultima_actualizacion: datetime = Field(default_factory=datetime.utcnow)
    # Podrías añadir más timestamps para diferentes etapas del pedido

    model_config = ConfigDict(from_attributes=True)


class OrderResponse(OrderInDB):  # Lo que se devuelve al cliente de la API
    # Podría ser igual a OrderInDB o seleccionar/transformar campos
    pass
