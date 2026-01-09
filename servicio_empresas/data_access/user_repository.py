import logging
from datetime import UTC, datetime

from database import get_users_collection
from pymongo import errors

logger = logging.getLogger(__name__)


async def crear_nueva_empresa(
    id_empresa: str, nombre_empresa: str, email: str, password_hash: str
) -> tuple[bool, str | dict]:
    try:
        collection = get_users_collection()
        existing = await collection.find_one({"id_empresa": id_empresa})
        if existing:
            return False, f"El id_empresa '{id_empresa}' ya existe."

        documento_empresa = {
            "_id": email,
            "id_empresa": id_empresa,
            "nombre_empresa": nombre_empresa,
            "password_hash": password_hash,
            "fecha_registro": datetime.now(UTC),
            "api_keys": [],
        }
        resultado = await collection.insert_one(documento_empresa)
        if resultado.inserted_id:
            return True, {
                "db_mensaje": "Empresa creada en DB.",
                "inserted_id": str(resultado.inserted_id),
            }
        else:
            return False, "No se pudo insertar la empresa en la DB."
    except errors.DuplicateKeyError:
        return False, f"El email '{email}' ya está registrado."
    except Exception as e:
        logger.error(f"Error al crear empresa '{id_empresa}': {e}", exc_info=True)
        return False, "Error interno al crear la empresa."


async def buscar_empresa_por_email(email: str) -> dict | None:
    try:
        collection = get_users_collection()
        return await collection.find_one({"_id": email})
    except Exception as e:
        logger.error(f"Error al buscar empresa por email '{email}': {e}", exc_info=True)
        return None


async def buscar_empresa_por_id_empresa(id_empresa: str) -> dict | None:
    try:
        collection = get_users_collection()
        return await collection.find_one({"id_empresa": id_empresa})
    except Exception as e:
        logger.error(f"Error al buscar empresa por id_empresa '{id_empresa}': {e}", exc_info=True)
        return None


async def agregar_api_key_a_empresa(
    id_empresa: str, key_id: str, key_hash: str, key_name: str, key_prefix: str
) -> bool:
    try:
        collection = get_users_collection()
        api_key_data = {
            "key_id": key_id,
            "key_hash": key_hash,
            "key_prefix": key_prefix,
            "name": key_name,
            "created_at": datetime.now(UTC),
            "last_used_at": None,
            "status": "active",
        }
        resultado = await collection.update_one(
            {"id_empresa": id_empresa}, {"$push": {"api_keys": api_key_data}}
        )
        return resultado.modified_count > 0
    except Exception as e:
        logger.error(f"Error agregando API key a empresa '{id_empresa}': {e}", exc_info=True)
        return False


async def obtener_api_keys_empresa(id_empresa: str) -> list:
    try:
        collection = get_users_collection()
        empresa = await collection.find_one({"id_empresa": id_empresa}, {"api_keys": 1, "_id": 0})
        if empresa and "api_keys" in empresa:
            return [
                {
                    "key_id": key.get("key_id"),
                    "name": key.get("name"),
                    "key_prefix": key.get("key_prefix"),
                    "created_at": key.get("created_at"),
                    "last_used_at": key.get("last_used_at"),
                    "status": key.get("status"),
                }
                for key in empresa["api_keys"]
                if key.get("status") == "active"
            ]
        return []
    except Exception as e:
        logger.error(f"Error obteniendo API keys de empresa '{id_empresa}': {e}", exc_info=True)
        return []


async def revocar_api_key_empresa(id_empresa: str, key_id: str) -> bool:
    try:
        collection = get_users_collection()
        resultado = await collection.update_one(
            {"id_empresa": id_empresa, "api_keys.key_id": key_id},
            {"$set": {"api_keys.$.status": "revoked", "api_keys.$.revoked_at": datetime.now(UTC)}},
        )
        return resultado.modified_count > 0
    except Exception as e:
        logger.error(
            f"Error revocando API key '{key_id}' de empresa '{id_empresa}': {e}", exc_info=True
        )
        return False


async def buscar_empresa_por_api_key_hash(key_hash_a_verificar: str) -> dict | None:
    try:
        collection = get_users_collection()
        empresa = await collection.find_one(
            {"api_keys": {"$elemMatch": {"key_hash": key_hash_a_verificar, "status": "active"}}}
        )
        return empresa
    except Exception as e:
        logger.error(f"Error buscando empresa por API key hash: {e}", exc_info=True)
        return None
