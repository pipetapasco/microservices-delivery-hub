import uuid
from datetime import UTC, datetime

from sqlalchemy import DECIMAL, Boolean, Column, Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from .session import Base

ESTADOS_DISPONIBILIDAD_VALIDOS = ["disponible", "no_disponible", "en_servicio"]


class ConductorDB(Base):
    __tablename__ = "conductores"

    id_conductor = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nombre_completo = Column(String, nullable=False, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    telefono = Column(String, unique=True, index=True, nullable=False)
    hash_contrasena = Column(String, nullable=False)
    fecha_registro = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    activo = Column(
        Boolean,
        default=True,
        comment="Indica si la cuenta del conductor está activa en la plataforma en general.",
    )  # Cuenta activa en la plataforma
    estado_validacion_general = Column(String, default="pendiente", index=True)
    fecha_ultima_modificacion_perfil = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    tipo_documento = Column(String, nullable=True)
    numero_documento = Column(String, nullable=True, index=True)
    direccion_residencia = Column(String, nullable=True)
    ciudad_residencia = Column(String, nullable=True, index=True)

    estado_disponibilidad = Column(
        String,
        default="no_disponible",
        nullable=False,
        index=True,
        comment="Estado operativo actual del conductor: disponible, no_disponible, en_servicio",
    )

    vehiculos = relationship(
        "VehiculoConductorDB", back_populates="conductor", cascade="all, delete-orphan"
    )
    documentos = relationship(
        "DocumentoConductorDB", back_populates="conductor", cascade="all, delete-orphan"
    )
    servicios_realizados = relationship("HistorialServicioDB", back_populates="conductor")


class VehiculoConductorDB(Base):
    __tablename__ = "vehiculos_conductor"
    id_vehiculo = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    id_conductor = Column(
        UUID(as_uuid=True), ForeignKey("conductores.id_conductor"), nullable=False, index=True
    )
    placa = Column(String, unique=True, nullable=False, index=True)
    marca = Column(String, nullable=True)
    modelo = Column(String, nullable=True)
    color = Column(String, nullable=True)
    ano = Column(Integer, nullable=True)
    soat_numero = Column(String, nullable=True)
    soat_fecha_vencimiento = Column(Date, nullable=True)
    tecnomecanica_numero = Column(String, nullable=True)
    tecnomecanica_fecha_vencimiento = Column(Date, nullable=True)
    activo = Column(
        Boolean,
        default=False,
        comment="Indica si este es el vehículo activo del conductor para servicios",
    )
    fecha_registro_vehiculo = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    conductor = relationship("ConductorDB", back_populates="vehiculos")
    servicios_con_este_vehiculo = relationship(
        "HistorialServicioDB", back_populates="vehiculo_usado"
    )


class DocumentoConductorDB(Base):
    __tablename__ = "documentos_conductor"
    id_documento = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    id_conductor = Column(
        UUID(as_uuid=True), ForeignKey("conductores.id_conductor"), nullable=False, index=True
    )
    tipo_documento = Column(String, nullable=False)
    url_documento = Column(String, nullable=False)
    estado_verificacion = Column(String, default="pendiente", index=True)
    fecha_subida = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    fecha_verificacion = Column(DateTime(timezone=True), nullable=True)
    comentarios_verificacion = Column(Text, nullable=True)
    conductor = relationship("ConductorDB", back_populates="documentos")


class HistorialServicioDB(Base):
    __tablename__ = "historial_servicios"
    id_servicio = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    id_conductor = Column(
        UUID(as_uuid=True), ForeignKey("conductores.id_conductor"), nullable=False, index=True
    )
    id_vehiculo_usado = Column(
        UUID(as_uuid=True), ForeignKey("vehiculos_conductor.id_vehiculo"), nullable=True
    )
    id_cliente = Column(String, nullable=True, index=True)
    tipo_servicio_realizado = Column(String, nullable=False)
    fecha_hora_solicitud = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    fecha_hora_inicio_viaje = Column(DateTime(timezone=True), nullable=True)
    fecha_hora_fin_viaje = Column(DateTime(timezone=True), nullable=True)
    origen_descripcion = Column(Text, nullable=True)
    origen_latitud = Column(DECIMAL, nullable=True)
    origen_longitud = Column(DECIMAL, nullable=True)
    destino_descripcion = Column(Text, nullable=True)
    destino_latitud = Column(DECIMAL, nullable=True)
    destino_longitud = Column(DECIMAL, nullable=True)
    tarifa_cobrada = Column(DECIMAL, nullable=True)
    metodo_pago_usado = Column(String, nullable=True)
    estado_servicio = Column(String, nullable=False, index=True)
    calificacion_a_cliente = Column(Integer, nullable=True)
    comentario_a_cliente = Column(Text, nullable=True)
    calificacion_de_cliente = Column(Integer, nullable=True)
    comentario_de_cliente = Column(Text, nullable=True)
    conductor = relationship("ConductorDB", back_populates="servicios_realizados")
    vehiculo_usado = relationship(
        "VehiculoConductorDB", back_populates="servicios_con_este_vehiculo"
    )
