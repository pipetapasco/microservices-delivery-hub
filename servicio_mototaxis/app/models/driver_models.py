import uuid
from datetime import date, datetime

from pydantic import (  # Añadir validator para Pydantic v1 style
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
)

POSIBLES_ESTADOS_DISPONIBILIDAD = ["disponible", "no_disponible", "en_servicio"]


class DriverBase(BaseModel):
    email: EmailStr = Field(..., example="conductor@example.com")
    nombre_completo: str = Field(..., min_length=3, example="Juan Pérez Rodríguez")
    telefono: str = Field(..., min_length=7, max_length=15, example="3001234567")
    tipo_documento: str | None = Field(
        None, example="CC", description="Tipo de documento de identidad"
    )
    numero_documento: str | None = Field(
        None, example="1234567890", description="Número de documento de identidad"
    )
    direccion_residencia: str | None = Field(
        None, example="Calle Falsa 123, Barrio Centro", description="Dirección de residencia"
    )
    ciudad_residencia: str | None = Field(
        None, example="Ciudad Ejemplo", description="Ciudad de residencia"
    )


class DriverCreateRequest(DriverBase):
    password: str = Field(..., min_length=8, example="micontraseñaFuerte123")


class DriverProfileUpdate(BaseModel):
    nombre_completo: str | None = Field(None, min_length=3, example="Juan Pérez Rodríguez")
    telefono: str | None = Field(None, min_length=7, max_length=15, example="3001234567")
    tipo_documento: str | None = Field(None, example="CC")
    numero_documento: str | None = Field(None, example="1234567890")
    direccion_residencia: str | None = Field(None, example="Calle Nueva 456")
    ciudad_residencia: str | None = Field(None, example="Otra Ciudad")


class DriverChangePasswordRequest(BaseModel):
    current_password: str = Field(..., min_length=8)
    new_password: str = Field(..., min_length=8)
    confirm_new_password: str = Field(..., min_length=8)

    @field_validator("confirm_new_password")
    def passwords_match(cls, v, values):
        if "new_password" in values.data and v != values.data["new_password"]:
            raise ValueError("La nueva contraseña y la confirmación no coinciden.")
        return v


class DriverStatusUpdate(BaseModel):
    estado_disponibilidad: str = Field(
        ..., description="Nuevo estado de disponibilidad del conductor."
    )

    @field_validator("estado_disponibilidad")
    def validar_estado_disponibilidad(cls, value):
        if value not in POSIBLES_ESTADOS_DISPONIBILIDAD:
            raise ValueError(
                f"Estado de disponibilidad inválido. Debe ser uno de: {', '.join(POSIBLES_ESTADOS_DISPONIBILIDAD)}"
            )
        return value


class VehicleBase(BaseModel):
    placa: str = Field(..., min_length=5, max_length=7, example="XYZ123")
    marca: str | None = Field(None, example="Honda")
    modelo: str | None = Field(None, example="CB160F")
    color: str | None = Field(None, example="Negro")
    ano: int | None = Field(None, ge=1900, le=datetime.now().year + 1, example=2022)
    soat_numero: str | None = Field(None, example="SOAT12345")
    soat_fecha_vencimiento: date | None = Field(None, example="2025-12-31")
    tecnomecanica_numero: str | None = Field(None, example="TECNO67890")
    tecnomecanica_fecha_vencimiento: date | None = Field(None, example="2025-06-30")


class VehicleCreate(VehicleBase):
    pass


class VehicleUpdate(BaseModel):
    placa: str | None = Field(None, min_length=5, max_length=7)
    marca: str | None = None
    modelo: str | None = None
    color: str | None = None
    ano: int | None = Field(None, ge=1900, le=datetime.now().year + 1)
    soat_numero: str | None = None
    soat_fecha_vencimiento: date | None = None
    tecnomecanica_numero: str | None = None
    tecnomecanica_fecha_vencimiento: date | None = None


class VehicleInDB(VehicleBase):
    id_vehiculo: uuid.UUID
    id_conductor: uuid.UUID
    activo: bool = Field(default=False)
    fecha_registro_vehiculo: datetime
    model_config = ConfigDict(from_attributes=True)


class VehicleResponse(VehicleBase):
    id_vehiculo: uuid.UUID
    id_conductor: uuid.UUID
    activo: bool
    fecha_registro_vehiculo: datetime
    model_config = ConfigDict(from_attributes=True)


class DriverInDB(DriverBase):
    id_conductor: uuid.UUID
    hashed_password: str
    fecha_registro: datetime
    activo: bool = Field(default=True)
    estado_validacion_general: str = Field(default="pendiente")
    estado_disponibilidad: str = Field(default="no_disponible")
    fecha_ultima_modificacion_perfil: datetime | None = None
    model_config = ConfigDict(from_attributes=True)


class Driver(DriverBase):
    id_conductor: uuid.UUID
    fecha_registro: datetime
    activo: bool
    estado_validacion_general: str
    estado_disponibilidad: str
    fecha_ultima_modificacion_perfil: datetime | None = None
    model_config = ConfigDict(from_attributes=True)


class DriverLoginRequest(BaseModel):
    email: EmailStr = Field(..., example="conductor@example.com")
    password: str = Field(..., example="micontraseñaFuerte123")
