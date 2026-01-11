from flask import Blueprint, jsonify, request

from core.exceptions import SecurityError, ServiceError, ValidationError
from services.auth_service import autenticar_empresa, registrar_empresa

auth_bp = Blueprint("auth_bp", __name__, url_prefix="/api/v1/auth")


@auth_bp.route("/register", methods=["POST"])
async def endpoint_registrar_empresa():
    """
    Registrar una nueva empresa
    ---
    tags:
      - Auth
    consumes:
      - application/json
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - nombre_empresa
            - email
            - password
          properties:
            nombre_empresa:
              type: string
              example: "Mi Restaurante"
            email:
              type: string
              example: "contacto@mirestaurante.com"
            password:
              type: string
              example: "password123"
    responses:
      201:
        description: Empresa registrada exitosamente
        schema:
          type: object
          properties:
            message:
              type: string
            id_empresa:
              type: string
      400:
        description: Error de validación
      500:
        description: Error interno del servidor
    """
    data = request.json
    if not data:
        return jsonify({"error": "Payload JSON requerido."}), 400

    try:
        resultado = await registrar_empresa(data)
        return jsonify(resultado), 201
    except ValidationError as e:
        return jsonify({"error": e.message, "detalles": e.details}), 400
    except ServiceError as e:
        return jsonify({"error": e.message, "detalles": e.details}), 500
    except Exception:
        return jsonify({"error": "Error interno del servidor"}), 500


@auth_bp.route("/login", methods=["POST"])
async def endpoint_login_empresa():
    """
    Iniciar sesión de empresa
    ---
    tags:
      - Auth
    consumes:
      - application/json
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - email
            - password
          properties:
            email:
              type: string
              example: "contacto@mirestaurante.com"
            password:
              type: string
              example: "password123"
    responses:
      200:
        description: Login exitoso
        schema:
          type: object
          properties:
            access_token:
              type: string
              description: JWT token para autenticación
      400:
        description: Error de validación
      401:
        description: Credenciales inválidas
      500:
        description: Error interno del servidor
    """
    data = request.json
    if not data:
        return jsonify({"error": "Payload JSON requerido."}), 400

    try:
        access_token = await autenticar_empresa(data)
        return jsonify(access_token=access_token), 200
    except ValidationError as e:
        return jsonify({"error": e.message, "detalles": e.details}), 400
    except SecurityError as e:
        return jsonify({"error": e.message}), 401
    except Exception:
        return jsonify({"error": "Error interno del servidor"}), 500

