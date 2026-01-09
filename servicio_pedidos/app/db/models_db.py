# servicio_pedidos/app/db/models_db.py
import uuid
from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID  # Usar JSONB para modificadores
from sqlalchemy.orm import relationship

# Importar las constantes de validación de los modelos Pydantic para referencia si es necesario
from ..models.order_models import ESTADOS_PEDIDO_VALIDOS, TIPOS_DE_SERVICIO_VALIDOS

# Importar la Base declarativa desde session.py
from .session import Base


class PedidoDB(Base):
    __tablename__ = "pedidos"

    id_pedido = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Información del cliente (obtenida del bot de WhatsApp)
    id_cliente_externo = Column(
        String,
        index=True,
        nullable=True,
        comment="ID del cliente en el sistema de origen, ej. WhatsApp ID",
    )
    nombre_cliente = Column(String, nullable=True)
    telefono_cliente = Column(String, nullable=True, index=True)

    tipo_servicio = Column(
        String,
        nullable=False,
        index=True,
        comment=f"Valores: {', '.join(TIPOS_DE_SERVICIO_VALIDOS)}",
    )

    # Origen
    origen_descripcion = Column(Text, nullable=True)
    origen_latitud = Column(Numeric(10, 7), nullable=True)  # Precisión para coordenadas
    origen_longitud = Column(Numeric(10, 7), nullable=True)

    # Destino
    destino_descripcion = Column(Text, nullable=False)  # Asumimos que siempre hay un destino
    destino_latitud = Column(Numeric(10, 7), nullable=True)
    destino_longitud = Column(Numeric(10, 7), nullable=True)

    # Para pedidos a empresas
    id_empresa_asociada = Column(
        String,
        nullable=True,
        index=True,
        comment="ID de la empresa/restaurante del servicio_empresas",
    )

    detalles_adicionales_pedido = Column(Text, nullable=True)
    metodo_pago_sugerido = Column(String, nullable=True)
    monto_estimado_pedido = Column(Numeric(12, 2), nullable=True)  # Ej: 1234567890.12
    monto_final_cobrado = Column(Numeric(12, 2), nullable=True)

    # Asignación y estado
    id_conductor_asignado = Column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
        comment="FK al id_conductor del servicio_mototaxis",
    )
    estado_pedido = Column(
        String,
        nullable=False,
        default="solicitado",
        index=True,
        comment=f"Valores: {', '.join(ESTADOS_PEDIDO_VALIDOS)}",
    )

    # Timestamps
    fecha_creacion_pedido = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    fecha_ultima_actualizacion = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )
    fecha_asignacion_conductor = Column(DateTime(timezone=True), nullable=True)
    fecha_estimada_entrega = Column(DateTime(timezone=True), nullable=True)
    fecha_entrega_real = Column(DateTime(timezone=True), nullable=True)  # O fecha_finalizacion_real

    notas_internas = Column(
        Text, nullable=True, comment="Notas para uso interno del sistema o administradores"
    )

    # Relación con items_pedido
    items = relationship("ItemPedidoDB", back_populates="pedido", cascade="all, delete-orphan")
    # Relación con logs de estado (opcional, para auditoría)
    # logs_estado = relationship("EstadoPedidoLogDB", back_populates="pedido", cascade="all, delete-orphan")


class ItemPedidoDB(Base):
    __tablename__ = "items_pedido"

    id_item_pedido = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    id_pedido = Column(
        UUID(as_uuid=True), ForeignKey("pedidos.id_pedido"), nullable=False, index=True
    )

    # Información del producto/ítem
    id_item_menu_empresa = Column(
        String,
        nullable=True,
        index=True,
        comment="ID del ítem en el sistema de la empresa (servicio_empresas)",
    )
    nombre_item = Column(String, nullable=False)
    cantidad = Column(Integer, nullable=False, default=1)
    precio_unitario_registrado = Column(
        Numeric(12, 2), nullable=True, comment="Precio al momento de crear el pedido"
    )

    # Para almacenar modificadores seleccionados, opciones, etc.
    # JSONB es específico de PostgreSQL y muy flexible. Text podría ser una alternativa más genérica si almacenas un string JSON.
    modificadores_seleccionados = Column(JSONB, nullable=True)

    notas_item = Column(Text, nullable=True)

    # Relación con pedido
    pedido = relationship("PedidoDB", back_populates="items")
