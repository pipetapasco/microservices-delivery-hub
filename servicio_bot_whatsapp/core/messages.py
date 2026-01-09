"""Centralized bot messages - eliminates hardcoded strings."""

WELCOME_MESSAGE = """¡Hola {name}! 👋 Soy tu asistente virtual. Ofrezco servicios de:
1️⃣ Mototaxi 🏍️
2️⃣ Domicilios 🛍️
3️⃣ Compras 🛒

Dime qué servicio necesitas o envía un mensaje de voz."""

PROCESSING_MESSAGE = "Estoy procesando tu solicitud, por favor espera un momento..."

AUDIO_NOT_UNDERSTOOD = "¡Hola {name}! Recibí tu audio, pero no pude entenderlo."

AUDIO_PROCESSING_ERROR = "¡Hola {name}! Hubo un problema al procesar tu audio."

UNSUPPORTED_MEDIA = "¡Hola {name}! Recibí un archivo, pero solo proceso audio o texto."

MESSAGE_NOT_UNDERSTOOD = "¡Hola {name}! No entendí tu mensaje."

AI_ERROR = "Lo siento {name}, tuve un problema con la IA."

SERVICE_TYPE_PROMPT = """Por favor, {name}, ¿qué tipo de servicio necesitas?
{services_list}"""

MISSING_FIELDS_PROMPT = (
    "¡Entendido, {name}! Para tu servicio de *{service_type}*, necesito: {missing_fields}."
)

ORDER_CONFIRMED = """¡Tu pedido de *{service_type}* ha sido recibido y está siendo procesado! 🏍️🛍️
Te mantendremos informado."""

ORDER_FAILED = "Lo siento, tuvimos un problema al enviar tu pedido. Intenta de nuevo más tarde."

SERVICE_OPTIONS = {
    "mototaxi": "Mototaxi",
    "domicilio": "Domicilios",
    "compras": "Compras",
    "otro": "Otro servicio",
}


def format_services_list() -> str:
    """Format the services list for display."""
    services = list(SERVICE_OPTIONS.items())
    lines = []
    for i, (_key, label) in enumerate(services, 1):
        lines.append(f"{i}. {label}")
    return "\n".join(lines)
