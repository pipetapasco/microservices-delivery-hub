"""Pydantic schemas for data validation."""

from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class IncomingMessagePayload(BaseModel):
    """Payload for incoming WhatsApp messages queued for processing."""

    sender_number: str = Field(..., description="WhatsApp number with prefix")
    profile_name: str | None = None
    message_body: str | None = None
    num_media: int = 0
    media_url: str | None = None
    media_content_type: str | None = None
    received_at: datetime = Field(default_factory=datetime.now)

    @field_validator("sender_number")
    @classmethod
    def validate_sender(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("sender_number cannot be empty")
        return v.strip()

    @field_validator("message_body")
    @classmethod
    def sanitize_message(cls, v: str | None) -> str | None:
        if v is None:
            return None
        sanitized = v.strip()[:2000]
        return sanitized if sanitized else None


class GeminiExtractedData(BaseModel):
    """Validated response from Gemini AI extraction."""

    tipo_servicio: str | None = None
    origen: str | None = None
    destino: str | None = None
    nombre_usuario: str | None = None
    telefono: str | None = None
    metodo_pago: str | None = None
    monto: str | None = None
    detalles_adicionales: str | None = None

    @field_validator("tipo_servicio")
    @classmethod
    def normalize_service_type(cls, v: str | None) -> str | None:
        if v is None:
            return None
        normalized = v.strip().lower()
        valid_services = ["mototaxi", "domicilio", "compras", "otro"]
        return normalized if normalized in valid_services else "otro"


class UserSession(BaseModel):
    """User session state stored in Redis."""

    last_seen: datetime = Field(default_factory=datetime.now)
    current_order_data: dict = Field(default_factory=dict)
    awaiting_more_info: bool = False
    is_processing: bool = False

    def is_expired(self, timeout_minutes: int = 60) -> bool:
        """Check if session has expired."""
        from datetime import timedelta

        return datetime.now() - self.last_seen > timedelta(minutes=timeout_minutes)

    def should_send_welcome(self, welcome_timeout_minutes: int = 20) -> bool:
        """Check if welcome message should be sent."""
        from datetime import timedelta

        if self.current_order_data or self.awaiting_more_info:
            return False
        return datetime.now() - self.last_seen > timedelta(minutes=welcome_timeout_minutes)


class OrderPayload(BaseModel):
    """Payload for order to be published to RabbitMQ."""

    id_cliente_externo: str
    nombre_cliente: str | None = None
    telefono_cliente: str
    tipo_servicio: str
    origen_descripcion: str | None = None
    destino_descripcion: str | None = None
    id_empresa_asociada: str | None = None
    detalles_adicionales_pedido: str | None = None
    metodo_pago_sugerido: str | None = None
    monto_estimado_pedido: float | None = None
    items_pedido: list = Field(default_factory=list)

    @field_validator("telefono_cliente")
    @classmethod
    def extract_phone_number(cls, v: str) -> str:
        if ":" in v:
            return v.split(":")[-1]
        return v
