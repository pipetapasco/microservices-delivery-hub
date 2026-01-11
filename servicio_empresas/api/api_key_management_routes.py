from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from core.exceptions import ServiceError, ValidationError
from services import api_key_service

api_key_bp = Blueprint("api_key_bp", __name__, url_prefix="/api/v1/company/api-keys")


def handle_exception(e):
    if isinstance(e, ValidationError):
        return jsonify({"error": e.message}), 400
    elif isinstance(e, ServiceError):
        return jsonify({"error": e.message}), 500
    else:
        return jsonify({"error": "Error interno"}), 500


@api_key_bp.route("/", methods=["POST"])
@jwt_required()
async def endpoint_generar_api_key():
    """
    Generar una nueva API Key
    ---
    tags:
      - API Keys
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
            - name
          properties:
            name:
              type: string
              description: Nombre descriptivo para la API Key
              example: "Producción App Móvil"
    responses:
      201:
        description: API Key generada exitosamente
        schema:
          type: object
          properties:
            mensaje:
              type: string
            api_key:
              type: string
              description: La API Key en texto plano (solo se muestra una vez)
            nombre_key:
              type: string
      400:
        description: Error de validación o token inválido
      401:
        description: No autorizado - Token JWT requerido
      500:
        description: Error interno del servidor
    """
    current_user = get_jwt_identity()
    id_empresa_autenticada = (
        current_user.get("id_empresa") if isinstance(current_user, dict) else current_user
    )

    if not id_empresa_autenticada:
        return jsonify({"error": "Identidad de empresa no encontrada en el token JWT."}), 400

    data = request.json
    if not data or not data.get("name"):
        return (
            jsonify({"error": "Se requiere el campo 'name' para la API key en el payload JSON."}),
            400,
        )

    key_name = data.get("name")

    try:
        api_key_plaintext = await api_key_service.generar_nueva_api_key(
            id_empresa_autenticada, key_name
        )
        return (
            jsonify(
                {
                    "mensaje": "API Key generada exitosamente. Guárdala en un lugar seguro, no se mostrará de nuevo.",
                    "api_key": api_key_plaintext,
                    "nombre_key": key_name,
                }
            ),
            201,
        )
    except Exception as e:
        return handle_exception(e)


@api_key_bp.route("/", methods=["GET"])
@jwt_required()
async def endpoint_listar_api_keys():
    """
    Listar todas las API Keys de la empresa
    ---
    tags:
      - API Keys
    security:
      - Bearer: []
    responses:
      200:
        description: Lista de API Keys (sin mostrar las claves en texto plano)
        schema:
          type: array
          items:
            type: object
            properties:
              id:
                type: string
              name:
                type: string
              created_at:
                type: string
                format: date-time
              last_used:
                type: string
                format: date-time
      400:
        description: Token JWT inválido
      401:
        description: No autorizado - Token JWT requerido
      500:
        description: Error interno del servidor
    """
    current_user = get_jwt_identity()
    id_empresa_autenticada = (
        current_user.get("id_empresa") if isinstance(current_user, dict) else current_user
    )

    if not id_empresa_autenticada:
        return jsonify({"error": "Identidad de empresa no encontrada en el token JWT."}), 400

    try:
        keys_metadata = await api_key_service.listar_api_keys_empresa(id_empresa_autenticada)
        return jsonify(keys_metadata), 200
    except Exception as e:
        return handle_exception(e)


@api_key_bp.route("/<key_id>", methods=["DELETE"])
@jwt_required()
async def endpoint_revocar_api_key(key_id: str):
    """
    Revocar una API Key existente
    ---
    tags:
      - API Keys
    security:
      - Bearer: []
    parameters:
      - in: path
        name: key_id
        type: string
        required: true
        description: ID de la API Key a revocar
    responses:
      200:
        description: API Key revocada exitosamente
        schema:
          type: object
          properties:
            mensaje:
              type: string
      400:
        description: Token JWT inválido o API Key no encontrada
      401:
        description: No autorizado - Token JWT requerido
      500:
        description: Error interno del servidor
    """
    current_user = get_jwt_identity()
    id_empresa_autenticada = (
        current_user.get("id_empresa") if isinstance(current_user, dict) else current_user
    )

    if not id_empresa_autenticada:
        return jsonify({"error": "Identidad de empresa no encontrada en el token JWT."}), 400

    try:
        await api_key_service.revocar_api_key(id_empresa_autenticada, key_id)
        return jsonify({"mensaje": f"API Key con ID '{key_id}' revocada exitosamente."}), 200
    except Exception as e:
        return handle_exception(e)
