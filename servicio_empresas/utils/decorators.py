from functools import wraps

from flask import g, jsonify, request

from services import api_key_service


def api_key_required(f):
    @wraps(f)
    async def decorated_function(*args, **kwargs):
        api_key = request.headers.get("X-API-Key")

        if not api_key:
            return jsonify({"error": "API Key no proporcionada en el header 'X-API-Key'."}), 401

        empresa_autenticada = await api_key_service.validar_api_key_y_obtener_empresa(api_key)

        if not empresa_autenticada:
            return jsonify({"error": "API Key inválida o no autorizada."}), 401

        g.empresa_autenticada_por_api_key = empresa_autenticada
        g.id_empresa_autenticada_por_api_key = empresa_autenticada.get("id_empresa")

        return await f(*args, **kwargs)

    return decorated_function
