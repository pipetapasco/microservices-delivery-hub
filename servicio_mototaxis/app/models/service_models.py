import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

POSIBLES_ESTADOS_SERVICIO = [
    "solicitado",
    "aceptado",
    "en_camino_origen",
    "en_origen",
    "viaje_iniciado",
    "en_destino",
    "completado",
    "cancelado_conductor",
    "cancelado_cliente",
    "problema_reportado",
]


class ServiceBase(BaseModel):
    id_cliente: str | None = Field(None, example="cliente_uuid_o_telefono")
    tipo_servicio_realizado: str = Field(..., example="mototaxi")

    origen_descripcion: str | None = Field(None, example="Parque Principal")
    origen_latitud: float | None = Field(None, example=10.46314)
    origen_longitud: float | None = Field(None, example=-73.25322)

    destino_descripcion: str | None = Field(None, example="Hospital Rosario Pumarejo")
    destino_latitud: float | None = Field(None, example=10.4742)
    destino_longitud: float | None = Field(None, example=-73.2458)

    tarifa_cobrada: float | None = Field(None, example=5000.00)
    metodo_pago_usado: str | None = Field(None, example="efectivo")
    estado_servicio: str = Field(..., example="completado")


class ServiceInDB(ServiceBase):
    id_servicio: uuid.UUID
    id_conductor: uuid.UUID
    id_vehiculo_usado: uuid.UUID | None = None

    fecha_hora_solicitud: datetime
    fecha_hora_inicio_viaje: datetime | None = None
    fecha_hora_fin_viaje: datetime | None = None

    calificacion_a_cliente: int | None = Field(None, ge=1, le=5)
    comentario_a_cliente: str | None = None
    calificacion_de_cliente: int | None = Field(None, ge=1, le=5)
    comentario_de_cliente: str | None = None

    model_config = ConfigDict(from_attributes=True)


class ServiceResponse(ServiceInDB):
    pass


class ServiceStatusUpdateRequest(BaseModel):
    nuevo_estado: str = Field(..., description="El nuevo estado al que se actualizará el servicio.")

    @field_validator("nuevo_estado")
    def validar_estado_servicio(cls, value):
        if value not in POSIBLES_ESTADOS_SERVICIO:
            raise ValueError(
                f"Estado de servicio inválido. Debe ser uno de: {', '.join(POSIBLES_ESTADOS_SERVICIO)}"
            )
        return value


class ServiceCreateForDriver(ServiceBase):
    id_conductor: uuid.UUID
    id_vehiculo_usado: uuid.UUID | None = None
