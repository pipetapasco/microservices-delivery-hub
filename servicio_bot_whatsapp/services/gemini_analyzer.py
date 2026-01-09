"""Gemini AI analyzer with JSON mode and Pydantic validation."""

import asyncio
from concurrent.futures import ThreadPoolExecutor

import config
import google.generativeai as genai
from logger import get_logger

from core.exceptions import ConfigurationError, GeminiAnalysisError
from core.schemas import GeminiExtractedData

logger = get_logger(__name__)

_model = None
_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="gemini")

EXTRACTION_PROMPT = """Extrae la siguiente información del mensaje del usuario.

Campos a extraer:
- "tipo_servicio": ("mototaxi", "compras", "domicilio", o "otro")
- "origen": dirección de inicio
- "destino": dirección de destino
- "nombre_usuario": nombre del cliente
- "telefono": teléfono de contacto
- "metodo_pago": ("efectivo", "transferencia", "nequi", "daviplata", "otro")
- "monto": valor del servicio
- "detalles_adicionales": información extra del pedido

Responde SOLO con JSON válido. Si un campo no está presente, omítelo o usa null.

Mensaje del usuario:
{user_message}"""


def _initialize_model() -> None:
    """Initialize Gemini model with JSON mode."""
    global _model

    if _model is not None:
        return

    if not config.GEMINI_API_KEY:
        raise ConfigurationError("GEMINI_API_KEY is required")

    try:
        genai.configure(api_key=config.GEMINI_API_KEY)

        generation_config = {
            "temperature": 0.1,
            "top_p": 0.95,
            "top_k": 1,
            "max_output_tokens": 500,
            "response_mime_type": "application/json",
        }

        safety_settings = [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
        ]

        _model = genai.GenerativeModel(
            model_name="gemini-2.0-flash",
            generation_config=generation_config,
            safety_settings=safety_settings,
        )
        logger.info("Gemini model initialized with JSON mode")

    except Exception as e:
        logger.error(f"Failed to initialize Gemini: {type(e).__name__}")
        raise ConfigurationError("Cannot initialize Gemini model") from e


def _analyze_sync(user_message: str) -> GeminiExtractedData:
    """Synchronous analysis (runs in thread pool)."""
    _initialize_model()

    if not _model:
        raise GeminiAnalysisError("Gemini model not available")

    if not user_message or not user_message.strip():
        raise GeminiAnalysisError("Empty message provided")

    prompt = EXTRACTION_PROMPT.format(user_message=user_message[:2000])

    try:
        response = _model.generate_content(prompt)

        if not response.parts:
            if response.prompt_feedback and response.prompt_feedback.block_reason:
                raise GeminiAnalysisError("Request blocked by safety policy")
            raise GeminiAnalysisError("Empty response from Gemini")

        json_text = ""
        for part in response.parts:
            if hasattr(part, "text") and part.text:
                json_text += part.text

        if not json_text.strip():
            raise GeminiAnalysisError("No text in Gemini response")

        import json

        data = json.loads(json_text)

        return GeminiExtractedData(**data)

    except json.JSONDecodeError as e:
        logger.error("JSON decode error from Gemini")
        raise GeminiAnalysisError("Invalid JSON from Gemini") from e
    except GeminiAnalysisError:
        raise
    except Exception as e:
        logger.error(f"Gemini analysis error: {type(e).__name__}")
        raise GeminiAnalysisError("Analysis failed") from e


async def analyze_message(user_message: str) -> GeminiExtractedData:
    """
    Analyze user message with Gemini AI.
    Runs in thread pool to avoid blocking async loop.
    Returns validated Pydantic model.
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_executor, _analyze_sync, user_message)


def get_model_status() -> bool:
    """Check if Gemini model is initialized."""
    return _model is not None
