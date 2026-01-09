import hashlib
import logging
import secrets
import uuid

from data_access import user_repository

from core.exceptions import AppValidationError, ServiceError

logger = logging.getLogger(__name__)

API_KEY_LENGTH = 32
API_KEY_PREFIX_LENGTH = 8


def _generate_api_key_string() -> str:
    return secrets.token_urlsafe(API_KEY_LENGTH)


def _hash_api_key(api_key: str) -> str:
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()


async def generar_nueva_api_key(id_empresa: str, key_name: str) -> str:
    if not key_name or not key_name.strip():
        raise AppValidationError("El nombre para la API key es requerido.")

    api_key_plaintext = _generate_api_key_string()
    api_key_hash = _hash_api_key(api_key_plaintext)
    key_id = str(uuid.uuid4())
    key_prefix = api_key_plaintext[:API_KEY_PREFIX_LENGTH]

    exito_db = await user_repository.agregar_api_key_a_empresa(
        id_empresa, key_id, api_key_hash, key_name, key_prefix
    )

    if exito_db:
        logger.info(f"Nueva API key generada para empresa '{id_empresa}', nombre: '{key_name}'")
        return api_key_plaintext
    else:
        logger.error(f"Error al guardar hash de API key para empresa '{id_empresa}'")
        raise ServiceError("Error interno al generar la API key. Intente de nuevo.")


async def listar_api_keys_empresa(id_empresa: str) -> list:
    return await user_repository.obtener_api_keys_empresa(id_empresa)


async def revocar_api_key(id_empresa: str, key_id_a_revocar: str) -> None:
    exito = await user_repository.revocar_api_key_empresa(id_empresa, key_id_a_revocar)
    if not exito:
        raise ServiceError(
            f"No se pudo revocar la API Key '{key_id_a_revocar}' o no fue encontrada."
        )


async def validar_api_key_y_obtener_empresa(api_key_proporcionada: str) -> dict | None:
    if not api_key_proporcionada:
        return None

    hash_a_buscar = _hash_api_key(api_key_proporcionada)
    empresa = await user_repository.buscar_empresa_por_api_key_hash(hash_a_buscar)

    if empresa:
        logger.info(f"API Key validada exitosamente para empresa ID: {empresa.get('id_empresa')}")
    else:
        logger.warning("API Key inválida o no encontrada.")
    return empresa
