from flask import Blueprint, current_app, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required

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

web_menu_bp = Blueprint("web_menu_bp", __name__, url_prefix="/panel/v1/menus")


@web_menu_bp.route("/", methods=["POST"])
@jwt_required()
async def web_reemplazar_menu_completo_empresa():
    """
    Reemplazar menú completo (Panel Web)
    ---
    tags:
      - Menus (Panel)
    security:
      - Bearer: []
    consumes:
      - application/json
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - id_empresa
            - items_menu
          properties:
            id_empresa:
              type: string
            items_menu:
              type: array
              items:
                type: object
    responses:
      201:
        description: Menú reemplazado exitosamente
      400:
        description: Error de validación
      403:
        description: No autorizado para esta empresa
    """
    id_empresa_jwt = get_jwt_identity()
    data = request.json
    if not data:
        return jsonify({"error": "Payload JSON vacío."}), 400

    id_empresa_payload = data.get("id_empresa")
    items_menu = data.get("items_menu")

    if not id_empresa_payload:
        return jsonify({"error": "'id_empresa' es requerido en el payload."}), 400
    if str(id_empresa_jwt) != str(id_empresa_payload):
        return jsonify({"error": "No autorizado para modificar el menú de esta empresa."}), 403

    if items_menu is None:
        return jsonify({"error": "'items_menu' es requerido y debe ser una lista."}), 400
    if not isinstance(items_menu, list):
        return jsonify({"error": "'items_menu' debe ser una lista."}), 400

    exito, resultado = await procesar_y_almacenar_menu_completo(
        id_empresa_payload, items_menu, origen_carga="panel_web_directo"
    )
    if exito:
        return jsonify(resultado), 201
    else:
        return jsonify(resultado), 400


@web_menu_bp.route("/<id_empresa_param>", methods=["GET"])
@jwt_required()
async def web_consultar_menu_completo_empresa(id_empresa_param: str):
    """
    Consultar menú completo (Panel Web)
    ---
    tags:
      - Menus (Panel)
    security:
      - Bearer: []
    parameters:
      - in: path
        name: id_empresa_param
        type: string
        required: true
    responses:
      200:
        description: Menú de la empresa
      403:
        description: No autorizado
      404:
        description: Menú no encontrado
    """
    id_empresa_jwt = get_jwt_identity()
    if str(id_empresa_jwt) != str(id_empresa_param):
        return jsonify({"error": "No autorizado para consultar este menú."}), 403

    menu_items = await obtener_menu_empresa(id_empresa_param)
    if menu_items is not None:
        return jsonify({"id_empresa": id_empresa_param, "items_menu": menu_items}), 200
    else:
        return jsonify({"error": f"Menú no encontrado para la empresa '{id_empresa_param}'."}), 404


@web_menu_bp.route("/via-url", methods=["POST"])
@jwt_required()
async def web_recibir_menu_completo_via_url():
    """
    Cargar menú desde URL (Panel Web)
    ---
    tags:
      - Menus (Panel)
    security:
      - Bearer: []
    consumes:
      - application/json
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - id_empresa
            - url_del_archivo
          properties:
            id_empresa:
              type: string
            url_del_archivo:
              type: string
    responses:
      202:
        description: Menú en proceso de carga
      400:
        description: Error de validación
      403:
        description: No autorizado
    """
    id_empresa_jwt = get_jwt_identity()
    data = request.json
    if not data:
        return jsonify({"error": "Payload JSON vacío."}), 400
    id_empresa_payload = data.get("id_empresa")
    url_del_archivo = data.get("url_del_archivo")
    if not id_empresa_payload:
        return jsonify({"error": "'id_empresa' es requerido."}), 400
    if str(id_empresa_jwt) != str(id_empresa_payload):
        return jsonify({"error": "No autorizado."}), 403
    if not url_del_archivo:
        return jsonify({"error": "'url_del_archivo' es requerido."}), 400

    exito, resultado = await procesar_menu_desde_url(id_empresa_payload, url_del_archivo)
    if exito:
        return jsonify(resultado), 202
    else:
        return jsonify(resultado), 400


ALLOWED_EXTENSIONS_WEB = {"json", "csv"}


def archivo_permitido_web(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS_WEB


@web_menu_bp.route("/upload-file", methods=["POST"])
@jwt_required()
async def web_subir_archivo_menu_completo():
    """
    Subir archivo de menú (Panel Web)
    ---
    tags:
      - Menus (Panel)
    security:
      - Bearer: []
    consumes:
      - multipart/form-data
    parameters:
      - in: formData
        name: menu_file
        type: file
        required: true
        description: Archivo JSON o CSV
      - in: formData
        name: id_empresa
        type: string
        required: false
        description: ID de empresa (opcional, se usa el del JWT)
    responses:
      202:
        description: Archivo procesado
      400:
        description: Error de validación
      403:
        description: Conflicto de ID de empresa
    """
    id_empresa_jwt = get_jwt_identity()
    if "menu_file" not in request.files:
        return jsonify({"error": "Falta 'menu_file'."}), 400
    archivo = request.files["menu_file"]
    id_empresa_form = request.form.get("id_empresa")
    if id_empresa_form and str(id_empresa_jwt) != str(id_empresa_form):
        return jsonify({"error": "Conflicto de ID de empresa."}), 403
    id_empresa_a_usar = id_empresa_jwt
    if archivo.filename == "":
        return jsonify({"error": "Archivo no seleccionado."}), 400
    if archivo and archivo_permitido_web(archivo.filename):
        exito, resultado = await procesar_archivo_menu_subido(
            current_app.config, id_empresa_a_usar, archivo
        )
        if exito:
            return jsonify(resultado), 202
        else:
            return jsonify(resultado), 400
    else:
        return jsonify({"error": "Tipo de archivo no permitido."}), 400


@web_menu_bp.route("/items", methods=["POST"])
@jwt_required()
async def web_agregar_nuevo_item():
    """
    Agregar nuevo ítem al menú (Panel Web)
    ---
    tags:
      - Menus (Panel)
    security:
      - Bearer: []
    consumes:
      - application/json
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          properties:
            nombre:
              type: string
            precio:
              type: number
            descripcion:
              type: string
            categoria:
              type: string
    responses:
      201:
        description: Ítem agregado
      400:
        description: Error de validación
    """
    id_empresa_jwt = get_jwt_identity()

    item_data = request.json
    if not item_data:
        return jsonify({"error": "Payload JSON del ítem es requerido."}), 400

    exito, resultado = await agregar_item_al_menu(id_empresa_jwt, item_data)
    if exito:
        return jsonify(resultado), 201
    else:
        return jsonify(resultado), 400


@web_menu_bp.route("/items/<item_uuid>", methods=["GET"])
@jwt_required()
async def web_obtener_item(item_uuid: str):
    """
    Obtener ítem específico (Panel Web)
    ---
    tags:
      - Menus (Panel)
    security:
      - Bearer: []
    parameters:
      - in: path
        name: item_uuid
        type: string
        required: true
    responses:
      200:
        description: Detalles del ítem
      404:
        description: Ítem no encontrado
    """
    id_empresa_jwt = get_jwt_identity()

    item = await obtener_item_especifico(id_empresa_jwt, item_uuid)
    if item:
        return jsonify(item), 200
    else:
        return jsonify({"error": f"Ítem '{item_uuid}' no encontrado para tu empresa."}), 404


@web_menu_bp.route("/items/<item_uuid>", methods=["PUT"])
@jwt_required()
async def web_actualizar_item(item_uuid: str):
    """
    Actualizar ítem del menú (Panel Web)
    ---
    tags:
      - Menus (Panel)
    security:
      - Bearer: []
    consumes:
      - application/json
    parameters:
      - in: path
        name: item_uuid
        type: string
        required: true
      - in: body
        name: body
        required: true
        schema:
          type: object
          properties:
            nombre:
              type: string
            precio:
              type: number
            descripcion:
              type: string
            categoria:
              type: string
    responses:
      200:
        description: Ítem actualizado
      400:
        description: Error de validación
      404:
        description: Ítem no encontrado
    """
    id_empresa_jwt = get_jwt_identity()

    datos_actualizacion = request.json
    if not datos_actualizacion:
        return jsonify({"error": "Payload JSON con datos de actualización es requerido."}), 400

    exito, resultado = await actualizar_item_menu(id_empresa_jwt, item_uuid, datos_actualizacion)
    if exito:
        return jsonify(resultado), 200
    else:
        status_code = 404 if "no encontrado" in resultado.get("error", "").lower() else 400
        return jsonify(resultado), status_code


@web_menu_bp.route("/items/<item_uuid>", methods=["DELETE"])
@jwt_required()
async def web_eliminar_item(item_uuid: str):
    """
    Eliminar ítem del menú (Panel Web)
    ---
    tags:
      - Menus (Panel)
    security:
      - Bearer: []
    parameters:
      - in: path
        name: item_uuid
        type: string
        required: true
    responses:
      200:
        description: Ítem eliminado
      404:
        description: Ítem no encontrado
    """
    id_empresa_jwt = get_jwt_identity()

    exito, resultado = await eliminar_item_menu(id_empresa_jwt, item_uuid)
    if exito:
        return jsonify(resultado), 200
    else:
        status_code = 404 if "no encontrado" in resultado.get("error", "").lower() else 400
        return jsonify(resultado), status_code
