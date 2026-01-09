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
