"""Dialogue manager - handles conversation flow and order building."""

from logger import get_logger

from core import messages
from core.schemas import GeminiExtractedData, OrderPayload, UserSession

logger = get_logger(__name__)

REQUIRED_FIELDS_PER_SERVICE = {
    "mototaxi": ["nombre_usuario", "origen", "destino", "metodo_pago"],
    "domicilio": ["nombre_usuario", "destino", "metodo_pago", "detalles_adicionales"],
    "compras": ["nombre_usuario", "detalles_adicionales", "destino", "metodo_pago"],
    "otro": ["nombre_usuario", "detalles_adicionales", "metodo_pago"],
}

POSSIBLE_SERVICES = ["mototaxi", "domicilio", "compras", "otro"]


class DialogueManager:
    """Manages conversation state and order building."""

    def __init__(self, session: UserSession, profile_name: str | None = None):
        self.session = session
        self.profile_name = profile_name or "tú"
        self._response_message: str | None = None

    @property
    def display_name(self) -> str:
        """Get sanitized display name for user."""
        name = self.profile_name[:50] if self.profile_name else "tú"
        return name.strip() or "tú"

    def should_send_welcome(self) -> bool:
        """Check if welcome message should be sent."""
        return self.session.should_send_welcome(welcome_timeout_minutes=20)

    def get_welcome_message(self) -> str:
        """Get formatted welcome message."""
        return messages.WELCOME_MESSAGE.format(name=self.display_name)

    def update_order_data(self, extracted: GeminiExtractedData) -> None:
        """Update session order data with extracted information."""
        data = extracted.model_dump(exclude_none=True)

        for key, value in data.items():
            if value and str(value).strip():
                cleaned = str(value).strip()[:500]
                self.session.current_order_data[key] = cleaned

    def get_next_prompt(self) -> tuple[bool, str | None]:
        """
        Determine what to ask the user next.
        Returns (is_complete, message).
        If is_complete is True, order is ready to submit.
        """
        service_type = self.session.current_order_data.get("tipo_servicio")

        if not service_type or service_type not in REQUIRED_FIELDS_PER_SERVICE:
            services_list = messages.format_services_list()
            message = messages.SERVICE_TYPE_PROMPT.format(
                name=self.display_name, services_list=services_list
            )
            return False, message

        required_fields = REQUIRED_FIELDS_PER_SERVICE.get(
            service_type, REQUIRED_FIELDS_PER_SERVICE["otro"]
        )
        missing = []

        for field in required_fields:
            value = self.session.current_order_data.get(field)
            if not value or not str(value).strip():
                missing.append(field.replace("_", " "))

        if missing:
            message = messages.MISSING_FIELDS_PROMPT.format(
                name=self.display_name,
                service_type=service_type.capitalize(),
                missing_fields=", ".join(missing),
            )
            return False, message

        return True, None

    def build_order_payload(self, sender_number: str) -> OrderPayload:
        """Build validated order payload from session data."""
        order_data = self.session.current_order_data

        monto = None
        monto_str = order_data.get("monto")
        if monto_str:
            try:
                clean_monto = "".join(c for c in str(monto_str) if c.isdigit() or c == ".")
                monto = float(clean_monto) if clean_monto else None
            except (ValueError, TypeError):
                pass

        items = []
        service_type = order_data.get("tipo_servicio", "otro")
        details = order_data.get("detalles_adicionales")

        if service_type in ["compras", "domicilio"] and details:
            items.append({"nombre_item": details, "cantidad": 1})

        return OrderPayload(
            id_cliente_externo=sender_number,
            nombre_cliente=order_data.get("nombre_usuario", self.profile_name),
            telefono_cliente=sender_number,
            tipo_servicio=service_type,
            origen_descripcion=order_data.get("origen"),
            destino_descripcion=order_data.get("destino"),
            id_empresa_asociada=order_data.get("id_empresa"),
            detalles_adicionales_pedido=details,
            metodo_pago_sugerido=order_data.get("metodo_pago"),
            monto_estimado_pedido=monto,
            items_pedido=items,
        )

    def get_confirmation_message(self, service_type: str) -> str:
        """Get order confirmation message."""
        return messages.ORDER_CONFIRMED.format(service_type=service_type)

    def get_error_message(self, error_type: str) -> str:
        """Get appropriate error message."""
        error_messages = {
            "audio_not_understood": messages.AUDIO_NOT_UNDERSTOOD,
            "audio_error": messages.AUDIO_PROCESSING_ERROR,
            "unsupported_media": messages.UNSUPPORTED_MEDIA,
            "message_not_understood": messages.MESSAGE_NOT_UNDERSTOOD,
            "ai_error": messages.AI_ERROR,
            "order_failed": messages.ORDER_FAILED,
        }
        template = error_messages.get(error_type, messages.MESSAGE_NOT_UNDERSTOOD)
        return template.format(name=self.display_name)

    def clear_order(self) -> None:
        """Clear current order data from session."""
        self.session.current_order_data = {}
        self.session.awaiting_more_info = False
