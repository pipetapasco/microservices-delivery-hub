from flask import Blueprint, current_app, g, jsonify, request
from utils.decorators import api_key_required

from core.exceptions import (
    ExternalAPIError,
    FileUploadError,
    ResourceNotFound,
    SecurityError,
    ServiceError,
    ValidationError,
)
from services.menu_data_service import (
    actualizar_item_menu,
    agregar_item_al_menu,
    eliminar_item_menu,
    obtener_item_especifico,
    obtener_menu_empresa,
    procesar_archivo_menu_subido,
    procesar_menu_desde_url,
    procesar_y_almacenar_menu_completo,
)

menu_api_bp = Blueprint("menu_api_bp", __name__, url_prefix="/api/v1/menus")


def handle_exception(e):
    if isinstance(e, ValidationError):
        return jsonify({"error": e.message, "detalles": e.details}), 400
    elif isinstance(e, SecurityError):
        return jsonify({"error": "Error de seguridad", "mensaje": e.message}), 403
    elif isinstance(e, ResourceNotFound):
        return jsonify({"error": e.message}), 404
    elif isinstance(e, FileUploadError):
        return jsonify({"error": "Error subiendo archivo", "mensaje": e.message}), 400
    elif isinstance(e, ExternalAPIError):
        return jsonify({"error": "Error en servicio externo", "mensaje": e.message}), 502
    elif isinstance(e, ServiceError):
        return (
            jsonify(
                {"error": "Error interno de servicio", "mensaje": e.message, "detalles": e.details}
            ),
            500,
        )
    else:
        return jsonify({"error": "Error interno inesperado"}), 500


@menu_api_bp.route("/", methods=["POST"])
@api_key_required
async def api_reemplazar_menu_completo_empresa():
    try:
        id_empresa_autenticada = getattr(g, "id_empresa_autenticada_por_api_key", None)
        data = request.json
        if not data:
            raise ValidationError("Payload JSON requerido")

        id_empresa_payload = data.get("id_empresa")
        items_menu = data.get("items_menu")

        if id_empresa_autenticada != id_empresa_payload:
            raise SecurityError("API Key no corresponde al id_empresa proporcionado")

        resultado = await procesar_y_almacenar_menu_completo(id_empresa_payload, items_menu)
        return jsonify(resultado), 201
    except Exception as e:
        return handle_exception(e)


@menu_api_bp.route("/<id_empresa_param>", methods=["GET"])
@api_key_required
async def api_consultar_menu_completo_empresa(id_empresa_param: str):
    try:
        id_empresa_autenticada = getattr(g, "id_empresa_autenticada_por_api_key", None)
        if id_empresa_autenticada != id_empresa_param:
            raise SecurityError("API Key no autorizada")

        menu_items = await obtener_menu_empresa(id_empresa_param)
        return jsonify({"id_empresa": id_empresa_param, "items_menu": menu_items}), 200
    except Exception as e:
        return handle_exception(e)


@menu_api_bp.route("/via-url", methods=["POST"])
@api_key_required
async def api_recibir_menu_via_url():
    try:
        id_empresa_autenticada = getattr(g, "id_empresa_autenticada_por_api_key", None)
        data = request.json
        if not data:
            raise ValidationError("Payload JSON requerido")

        id_empresa_payload = data.get("id_empresa")
        url_del_archivo = data.get("url_del_archivo")

        if id_empresa_autenticada != id_empresa_payload:
            raise SecurityError("API Key no corresponde")

        resultado = await procesar_menu_desde_url(id_empresa_payload, url_del_archivo)
        return jsonify(resultado), 202
    except Exception as e:
        return handle_exception(e)


ALLOWED_EXTENSIONS = {"json", "csv"}


def archivo_permitido(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


@menu_api_bp.route("/upload-file", methods=["POST"])
@api_key_required
async def api_subir_archivo_menu():
    try:
        id_empresa_autenticada = getattr(g, "id_empresa_autenticada_por_api_key", None)

        if "menu_file" not in request.files:
            raise ValidationError("Falta el archivo 'menu_file'")

        archivo = request.files["menu_file"]
        id_empresa_form = request.form.get("id_empresa")

        if not id_empresa_form:
            raise ValidationError("'id_empresa' es requerido en form-data")
        if id_empresa_autenticada != id_empresa_form:
            raise SecurityError("API Key no corresponde")
        if archivo.filename == "":
            raise ValidationError("Archivo no seleccionado")

        if not archivo_permitido(archivo.filename):
            raise ValidationError("Tipo de archivo no permitido (solo .json o .csv)")

        resultado = await procesar_archivo_menu_subido(current_app.config, id_empresa_form, archivo)
        return jsonify(resultado), 202
    except Exception as e:
        return handle_exception(e)


@menu_api_bp.route("/<id_empresa>/items", methods=["POST"])
@api_key_required
async def api_agregar_nuevo_item(id_empresa: str):
    try:
        id_empresa_autenticada = getattr(g, "id_empresa_autenticada_por_api_key", None)
        if id_empresa_autenticada != id_empresa:
            raise SecurityError("API Key no autorizada")

        item_data = request.json
        resultado = await agregar_item_al_menu(id_empresa, item_data)
        return jsonify(resultado), 201
    except Exception as e:
        return handle_exception(e)


@menu_api_bp.route("/<id_empresa>/items/<item_uuid>", methods=["GET"])
@api_key_required
async def api_obtener_item(id_empresa: str, item_uuid: str):
    try:
        id_empresa_autenticada = getattr(g, "id_empresa_autenticada_por_api_key", None)
        if id_empresa_autenticada != id_empresa:
            raise SecurityError("API Key no autorizada")

        item = await obtener_item_especifico(id_empresa, item_uuid)
        return jsonify(item), 200
    except Exception as e:
        return handle_exception(e)


@menu_api_bp.route("/<id_empresa>/items/<item_uuid>", methods=["PUT"])
@api_key_required
async def api_actualizar_item(id_empresa: str, item_uuid: str):
    try:
        id_empresa_autenticada = getattr(g, "id_empresa_autenticada_por_api_key", None)
        if id_empresa_autenticada != id_empresa:
            raise SecurityError("API Key no autorizada")

        datos_actualizacion = request.json
        resultado = await actualizar_item_menu(id_empresa, item_uuid, datos_actualizacion)
        return jsonify(resultado), 200
    except Exception as e:
        return handle_exception(e)


@menu_api_bp.route("/<id_empresa>/items/<item_uuid>", methods=["DELETE"])
@api_key_required
async def api_eliminar_item(id_empresa: str, item_uuid: str):
    try:
        id_empresa_autenticada = getattr(g, "id_empresa_autenticada_por_api_key", None)
        if id_empresa_autenticada != id_empresa:
            raise SecurityError("API Key no autorizada")

        resultado = await eliminar_item_menu(id_empresa, item_uuid)
        return jsonify(resultado), 200
    except Exception as e:
        return handle_exception(e)
