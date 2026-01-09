import csv
import io
import ipaddress
import json
import logging
import socket
import tempfile
import uuid
from urllib.parse import urlparse

import httpx
from data_access import menu_repository
from pydantic import ValidationError
from schemas import ItemMenu, ItemMenuUpdate

from core.exceptions import (
    ExternalAPIError,
    FileUploadError,
    ResourceNotFound,
    SecurityError,
    ServiceError,
    ValidationError as AppValidationError,
)

logger = logging.getLogger(__name__)

MAX_MEMORY_FILE_SIZE = 10 * 1024 * 1024


def _convert_pydantic_errors_to_list(validation_error: ValidationError) -> list[str]:
    errors = []
    for error in validation_error.errors():
        field = " -> ".join(str(loc) for loc in error["loc"])
        msg = error["msg"]
        errors.append(f"Campo '{field}': {msg}")
    return errors


def _validate_item_with_pydantic(item_data: dict, is_update: bool = False) -> dict:
    try:
        if is_update:
            validated = ItemMenuUpdate.model_validate(item_data)
        else:
            validated = ItemMenu.model_validate(item_data)
        return validated.model_dump(exclude_none=True)
    except ValidationError as e:
        error_list = _convert_pydantic_errors_to_list(e)
        raise AppValidationError("Error de validación de esquema", details={"errors": error_list})


def _parse_csv_row_to_item(row: dict) -> dict:
    return {
        "nombre": row.get("nombre_producto") or row.get("nombre"),
        "descripcion": row.get("descripcion_producto") or row.get("descripcion"),
        "precio_base": float(row.get("precio", 0)) if row.get("precio") else 0.0,
        "moneda": row.get("moneda", "COP"),
        "categoria_nombre": row.get("categoria"),
        "disponible": row.get("disponible", "true").lower() == "true",
        "id_externo_item": row.get("sku"),
    }


def _validate_url_security(url: str) -> None:
    parsed = urlparse(url)

    if parsed.scheme not in ("http", "https"):
        raise SecurityError(f"Esquema de URL no permitido: {parsed.scheme}")

    hostname = parsed.hostname
    if not hostname:
        raise SecurityError("URL inválida: no se pudo extraer el hostname")

    try:
        ip = socket.gethostbyname(hostname)
        ip_obj = ipaddress.ip_address(ip)

        if ip_obj.is_loopback:
            raise SecurityError(
                f"Intento de SSRF bloqueado: Acceso a Loopback ({hostname} -> {ip})"
            )
        if ip_obj.is_private:
            raise SecurityError(
                f"Intento de SSRF bloqueado: Acceso a IP Privada ({hostname} -> {ip})"
            )
        if ip_obj.is_link_local:
            raise SecurityError(
                f"Intento de SSRF bloqueado: Acceso a Link-Local ({hostname} -> {ip})"
            )
        if ip_obj.is_multicast:
            raise SecurityError(
                f"Intento de SSRF bloqueado: Acceso a Multicast ({hostname} -> {ip})"
            )

    except socket.gaierror:
        raise ExternalAPIError(f"No se pudo resolver el hostname: {hostname}")
    except ValueError:
        raise SecurityError(f"Dirección IP inválida resuelta: {ip}")


async def procesar_y_almacenar_menu_completo(
    id_empresa: str, items_menu_data: list, origen_carga: str = "directa"
) -> dict:
    logger.info(
        f"Procesando menú COMPLETO para id_empresa '{id_empresa}' vía carga {origen_carga}."
    )

    if not id_empresa or not id_empresa.strip():
        raise AppValidationError("Se requiere 'id_empresa'.")
    if not isinstance(items_menu_data, list):
        raise AppValidationError("'items_menu' debe ser una lista.")

    errores_globales = []
    items_validados_con_uuid = []

    if not items_menu_data:
        exito_db, res_db = await menu_repository.vaciar_menu_empresa_db(id_empresa)
        if not exito_db:
            raise ServiceError("Error DB al vaciar menú.", details=res_db)
        return {"mensaje": "Menú vaciado correctamente."}

    for idx, item_data in enumerate(items_menu_data):
        if not isinstance(item_data, dict):
            errores_globales.append(f"Ítem {idx + 1}: Cada ítem debe ser un objeto JSON.")
            continue

        if "item_uuid" not in item_data or not item_data["item_uuid"]:
            item_data["item_uuid"] = str(uuid.uuid4())

        try:
            _validate_item_with_pydantic(item_data, is_update=False)

            item_data_with_uuid = {**item_data}
            items_validados_con_uuid.append(item_data_with_uuid)

        except AppValidationError as e:
            for err in e.details.get("errors", []):
                errores_globales.append(f"Ítem {idx + 1}: {err}")

    if errores_globales:
        raise AppValidationError(
            "Errores de validación en los ítems", details={"errors": errores_globales}
        )

    exito_db, res_db = await menu_repository.guardar_o_actualizar_menu_completo(
        id_empresa, items_validados_con_uuid
    )
    if exito_db:
        return {
            "mensaje": f"Menú completo para '{id_empresa}' procesado. {len(items_validados_con_uuid)} ítems validados.",
            "db_info": res_db.get("db_mensaje", ""),
        }
    else:
        raise ServiceError("Error al guardar menú completo en DB.", details=res_db)


async def obtener_menu_empresa(id_empresa: str) -> list:
    menu = await menu_repository.buscar_menu_por_id_empresa(id_empresa)
    if menu is None:
        raise ResourceNotFound(f"No se encontró menú para la empresa '{id_empresa}'")
    return menu


async def agregar_item_al_menu(id_empresa: str, nuevo_item_data: dict) -> dict:
    nuevo_item_data["item_uuid"] = str(uuid.uuid4())

    _validate_item_with_pydantic(nuevo_item_data, is_update=False)

    exito_db, resultado_db = await menu_repository.agregar_item_a_menu_db(
        id_empresa, nuevo_item_data
    )
    if exito_db:
        return {
            "mensaje": "Ítem agregado exitosamente al menú.",
            "item_uuid": nuevo_item_data["item_uuid"],
            "db_info": resultado_db,
        }
    else:
        raise ServiceError("Error al agregar el ítem a la base de datos.", details=resultado_db)


async def obtener_item_especifico(id_empresa: str, item_uuid: str) -> dict:
    item = await menu_repository.buscar_item_en_menu_db(id_empresa, item_uuid)
    if not item:
        raise ResourceNotFound(f"Ítem '{item_uuid}' no encontrado.")
    return item


async def actualizar_item_menu(id_empresa: str, item_uuid: str, datos_actualizacion: dict) -> dict:
    if not datos_actualizacion:
        raise AppValidationError("No se proporcionaron datos para actualizar.")

    datos_actualizacion.pop("item_uuid", None)
    datos_actualizacion.pop("id_empresa", None)

    _validate_item_with_pydantic(datos_actualizacion, is_update=True)

    exito_db, resultado_db = await menu_repository.actualizar_item_en_menu_db(
        id_empresa, item_uuid, datos_actualizacion
    )
    if exito_db:
        return {"mensaje": f"Ítem '{item_uuid}' actualizado exitosamente.", "db_info": resultado_db}
    else:
        if "no encontrado" in str(resultado_db).lower():
            raise ResourceNotFound(
                f"Ítem '{item_uuid}' no encontrado para actualizar.", details=resultado_db
            )
        raise ServiceError(f"No se pudo actualizar el ítem '{item_uuid}'.", details=resultado_db)


async def eliminar_item_menu(id_empresa: str, item_uuid: str) -> dict:
    exito_db, resultado_db = await menu_repository.eliminar_item_de_menu_db(id_empresa, item_uuid)
    if exito_db:
        return {"mensaje": f"Ítem '{item_uuid}' eliminado exitosamente.", "db_info": resultado_db}
    else:
        if "no encontrado" in str(resultado_db).lower():
            raise ResourceNotFound(
                f"Ítem '{item_uuid}' no encontrado para eliminar.", details=resultado_db
            )
        raise ServiceError(f"No se pudo eliminar el ítem '{item_uuid}'.", details=resultado_db)


async def _download_file_streaming(url: str) -> tuple[str, str]:
    _validate_url_security(url)

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            async with client.stream("GET", url, follow_redirects=True) as response:
                response.raise_for_status()
                content_type = response.headers.get("Content-Type", "").lower()

                chunks = []
                total_size = 0
                async for chunk in response.aiter_bytes(chunk_size=8192):
                    total_size += len(chunk)
                    if total_size > MAX_MEMORY_FILE_SIZE:
                        raise FileUploadError(
                            f"Archivo de URL excede el límite de {MAX_MEMORY_FILE_SIZE/1024/1024}MB"
                        )
                    chunks.append(chunk)

                content = b"".join(chunks).decode("utf-8")
                logger.info(f"Archivo descargado exitosamente: {total_size} bytes")
                return content, content_type

    except httpx.HTTPStatusError as e:
        logger.error(f"[NETWORK] Error HTTP: {e}", exc_info=True)
        raise ExternalAPIError(f"Error HTTP al descargar: {e.response.status_code}")
    except httpx.RequestError as e:
        logger.error(f"[NETWORK] Error de conexión: {e}", exc_info=True)
        raise ExternalAPIError("Error de conexión al descargar archivo")
    except UnicodeDecodeError:
        raise AppValidationError("El archivo descargado no es texto válido UTF-8")


def _parse_json_content(content: str) -> list:
    try:
        data = json.loads(content)
        if isinstance(data, list):
            return data
        elif (
            isinstance(data, dict) and "items_menu" in data and isinstance(data["items_menu"], list)
        ):
            return data["items_menu"]
        else:
            raise AppValidationError(
                "El JSON no tiene el formato esperado (debe ser lista o {items_menu: [...]})"
            )
    except json.JSONDecodeError:
        raise AppValidationError("Error al decodificar JSON: formato inválido")


def _parse_csv_content(content: str) -> list:
    try:
        items = []
        csvfile = io.StringIO(content)
        reader = csv.DictReader(csvfile)
        for row in reader:
            items.append(_parse_csv_row_to_item(row))
        if not items:
            raise AppValidationError("El CSV está vacío o no tiene filas válidas")
        return items
    except Exception as e:
        raise AppValidationError(f"Error al procesar CSV: {e}")


async def procesar_menu_desde_url(id_empresa: str, url_del_archivo: str) -> dict:
    if not id_empresa:
        raise AppValidationError("Se requiere 'id_empresa'.")
    if not url_del_archivo:
        raise AppValidationError("Se requiere 'url_del_archivo'.")

    content, content_type = await _download_file_streaming(url_del_archivo)

    items_menu_extraidos = []
    if "application/json" in content_type or url_del_archivo.lower().endswith(".json"):
        items_menu_extraidos = _parse_json_content(content)
    elif "text/csv" in content_type or url_del_archivo.lower().endswith(".csv"):
        items_menu_extraidos = _parse_csv_content(content)
    else:
        raise AppValidationError("Tipo de archivo no soportado (solo JSON o CSV)")

    return await procesar_y_almacenar_menu_completo(
        id_empresa, items_menu_extraidos, origen_carga="URL"
    )


async def _read_spooled_file(spooled_file) -> str:
    try:
        spooled_file.seek(0)
        content = spooled_file.read().decode("utf-8-sig")
        return content
    except UnicodeDecodeError:
        raise AppValidationError("El archivo no es texto válido UTF-8")


async def procesar_archivo_menu_subido(app_config_flask, id_empresa: str, archivo_subido) -> dict:
    if not id_empresa:
        raise AppValidationError("Se requiere 'id_empresa'.")
    if not archivo_subido or not archivo_subido.filename:
        raise AppValidationError("No se proporcionó ningún archivo.")

    try:
        with tempfile.SpooledTemporaryFile(max_size=MAX_MEMORY_FILE_SIZE, mode="w+b") as temp_file:
            size = 0
            while True:
                chunk = archivo_subido.stream.read(8192)
                if not chunk:
                    break
                size += len(chunk)
                if size > MAX_MEMORY_FILE_SIZE:
                    raise FileUploadError(
                        f"El archivo excede el límite de {MAX_MEMORY_FILE_SIZE/1024/1024}MB"
                    )
                temp_file.write(chunk)

            # Reset pointer
            temp_file.seek(0)
            content = temp_file.read().decode("utf-8-sig")

        items_menu_extraidos = []
        if archivo_subido.filename.lower().endswith(".json"):
            items_menu_extraidos = _parse_json_content(content)
        elif archivo_subido.filename.lower().endswith(".csv"):
            items_menu_extraidos = _parse_csv_content(content)
        else:
            raise AppValidationError("Tipo de archivo no soportado (.json o .csv)")

        result = await procesar_y_almacenar_menu_completo(
            id_empresa, items_menu_extraidos, origen_carga="subida_directa"
        )
        return result

    except FileUploadError:
        raise
    except AppValidationError:
        raise
    except Exception as e:
        logger.error(f"[UNEXPECTED] Error procesando archivo subido: {e}", exc_info=True)
        raise ServiceError("Error interno procesando el archivo subido")
