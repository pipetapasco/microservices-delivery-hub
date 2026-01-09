import logging
from datetime import UTC, datetime

from database import get_menus_collection, get_users_collection

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
        return resultado.inserted_id is not None, {
            "db_mensaje": "Empresa creada.",
            "inserted_id": str(resultado.inserted_id),
        }
    except Exception as e:
        logger.error(f"Error al crear empresa: {e}", exc_info=True)
        return False, "Error interno al crear la empresa."


async def buscar_empresa_por_email(email: str) -> dict | None:
    try:
        return await get_users_collection().find_one({"_id": email})
    except Exception as e:
        logger.error(f"Error buscando empresa por email '{email}': {e}", exc_info=True)
        return None


async def buscar_empresa_por_id_empresa(id_empresa: str) -> dict | None:
    try:
        return await get_users_collection().find_one({"id_empresa": id_empresa})
    except Exception as e:
        logger.error(f"Error buscando empresa por id '{id_empresa}': {e}", exc_info=True)
        return None


async def agregar_api_key_a_empresa(
    id_empresa: str, key_id: str, key_hash: str, key_name: str, key_prefix: str
) -> bool:
    try:
        api_key_data = {
            "key_id": key_id,
            "key_hash": key_hash,
            "key_prefix": key_prefix,
            "name": key_name,
            "created_at": datetime.now(UTC),
            "last_used_at": None,
            "status": "active",
        }
        resultado = await get_users_collection().update_one(
            {"id_empresa": id_empresa}, {"$push": {"api_keys": api_key_data}}
        )
        return resultado.modified_count > 0
    except Exception as e:
        logger.error(f"Error agregando API key a '{id_empresa}': {e}", exc_info=True)
        return False


async def obtener_api_keys_empresa(id_empresa: str) -> list:
    try:
        empresa = await get_users_collection().find_one(
            {"id_empresa": id_empresa}, {"api_keys": 1, "_id": 0}
        )
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
        logger.error(f"Error obteniendo API keys de '{id_empresa}': {e}", exc_info=True)
        return []


async def revocar_api_key_empresa(id_empresa: str, key_id: str) -> bool:
    try:
        resultado = await get_users_collection().update_one(
            {"id_empresa": id_empresa, "api_keys.key_id": key_id},
            {"$set": {"api_keys.$.status": "revoked", "api_keys.$.revoked_at": datetime.now(UTC)}},
        )
        return resultado.modified_count > 0
    except Exception as e:
        logger.error(f"Error revocando API key '{key_id}' de '{id_empresa}': {e}", exc_info=True)
        return False


async def buscar_empresa_por_api_key_hash(key_hash_a_verificar: str) -> dict | None:
    try:
        return await get_users_collection().find_one(
            {"api_keys": {"$elemMatch": {"key_hash": key_hash_a_verificar, "status": "active"}}}
        )
    except Exception as e:
        logger.error(f"Error buscando empresa por API key hash: {e}", exc_info=True)
        return None


async def guardar_o_actualizar_menu_completo(
    id_empresa: str, items_menu_con_uuid: list
) -> tuple[bool, dict]:
    try:
        collection = get_menus_collection()
        resultado_db = await collection.replace_one(
            {"id_empresa": id_empresa},
            {
                "id_empresa": id_empresa,
                "items_menu": items_menu_con_uuid,
                "ultima_actualizacion": datetime.now(UTC),
            },
            upsert=True,
        )
        msg = f"Menú completo para '{id_empresa}' guardado/actualizado."
        return resultado_db.acknowledged, {
            "db_mensaje": msg,
            "upserted_id": str(resultado_db.upserted_id) if resultado_db.upserted_id else None,
        }
    except Exception as e:
        logger.error(f"Error DB (menu completo) para '{id_empresa}': {e}", exc_info=True)
        return False, {"db_error": "Error interno al guardar el menú."}


async def vaciar_menu_empresa_db(id_empresa: str) -> tuple[bool, dict]:
    try:
        collection = get_menus_collection()
        resultado_db = await collection.update_one(
            {"id_empresa": id_empresa},
            {"$set": {"items_menu": [], "ultima_actualizacion": datetime.now(UTC)}},
            upsert=True,
        )
        return resultado_db.acknowledged, {"db_mensaje": f"Menú para '{id_empresa}' vaciado en DB."}
    except Exception as e:
        logger.error(f"Error DB (vaciar menu) para '{id_empresa}': {e}", exc_info=True)
        return False, {"db_error": "Error interno al vaciar el menú."}


async def buscar_menu_por_id_empresa(id_empresa: str) -> list | None:
    try:
        documento_empresa = await get_menus_collection().find_one({"id_empresa": id_empresa})
        if documento_empresa and "items_menu" in documento_empresa:
            return documento_empresa["items_menu"]
        return None
    except Exception as e:
        logger.error(f"Error obteniendo menú de '{id_empresa}': {e}", exc_info=True)
        return None


async def agregar_item_a_menu_db(id_empresa: str, item_data_con_uuid: dict) -> tuple[bool, dict]:
    try:
        collection = get_menus_collection()
        resultado_db = await collection.update_one(
            {"id_empresa": id_empresa},
            {
                "$push": {"items_menu": item_data_con_uuid},
                "$set": {"ultima_actualizacion": datetime.now(UTC)},
            },
            upsert=True,
        )
        if resultado_db.acknowledged:
            if resultado_db.upserted_id:
                logger.info(f"Nuevo documento de menú creado para '{id_empresa}'.")
            return True, {
                "db_mensaje": "Ítem añadido al menú.",
                "item_uuid": item_data_con_uuid.get("item_uuid"),
            }
        else:
            return False, {"db_error": "La operación de agregar ítem no fue reconocida."}
    except Exception as e:
        logger.error(f"Error DB (agregar item) para '{id_empresa}': {e}", exc_info=True)
        return False, {"db_error": "Error interno al agregar el ítem."}


async def buscar_item_en_menu_db(id_empresa: str, item_uuid: str) -> dict | None:
    try:
        collection = get_menus_collection()
        documento_empresa = await collection.find_one(
            {"id_empresa": id_empresa, "items_menu.item_uuid": item_uuid},
            {"_id": 0, "items_menu.$": 1},
        )
        if (
            documento_empresa
            and "items_menu" in documento_empresa
            and documento_empresa["items_menu"]
        ):
            return documento_empresa["items_menu"][0]
        return None
    except Exception as e:
        logger.error(
            f"Error buscando ítem '{item_uuid}' en menú de '{id_empresa}': {e}", exc_info=True
        )
        return None


async def actualizar_item_en_menu_db(
    id_empresa: str, item_uuid: str, datos_actualizacion_item: dict
) -> tuple[bool, dict]:
    try:
        collection = get_menus_collection()
        campos_a_actualizar = {
            f"items_menu.$.{key}": value
            for key, value in datos_actualizacion_item.items()
            if key not in ["item_uuid", "id_empresa"]
        }

        if not campos_a_actualizar:
            return False, {"db_error": "No hay campos válidos para actualizar."}

        campos_a_actualizar["items_menu.$.ultima_modificacion_item"] = datetime.now(UTC)

        resultado_db = await collection.update_one(
            {"id_empresa": id_empresa, "items_menu.item_uuid": item_uuid},
            {"$set": campos_a_actualizar},
        )
        if resultado_db.matched_count > 0:
            if resultado_db.modified_count > 0:
                return True, {"db_mensaje": f"Ítem '{item_uuid}' actualizado."}
            else:
                return True, {"db_mensaje": f"Ítem '{item_uuid}' encontrado pero sin cambios."}
        else:
            return False, {"db_error": f"Ítem '{item_uuid}' no encontrado."}
    except Exception as e:
        logger.error(
            f"Error DB (actualizar item) para '{id_empresa}', ítem '{item_uuid}': {e}",
            exc_info=True,
        )
        return False, {"db_error": "Error interno al actualizar el ítem."}


async def eliminar_item_de_menu_db(id_empresa: str, item_uuid: str) -> tuple[bool, dict]:
    try:
        collection = get_menus_collection()
        resultado_db = await collection.update_one(
            {"id_empresa": id_empresa}, {"$pull": {"items_menu": {"item_uuid": item_uuid}}}
        )
        if resultado_db.modified_count > 0:
            return True, {"db_mensaje": f"Ítem '{item_uuid}' eliminado."}
        else:
            return False, {"db_error": f"Ítem '{item_uuid}' no encontrado."}
    except Exception as e:
        logger.error(
            f"Error DB (eliminar item) para '{id_empresa}', ítem '{item_uuid}': {e}", exc_info=True
        )
        return False, {"db_error": "Error interno al eliminar el ítem."}
