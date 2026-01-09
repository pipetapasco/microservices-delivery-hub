import logging
from datetime import timedelta

from data_access import user_repository
from flask_jwt_extended import create_access_token
from pydantic import ValidationError
from schemas import EmpresaLogin, EmpresaRegistro
from werkzeug.security import check_password_hash, generate_password_hash

from core.exceptions import (
    ResourceNotFound,
    SecurityError,
    ServiceError,
    ValidationError as AppValidationError,
)

logger = logging.getLogger(__name__)

ACCESS_EXPIRES = timedelta(hours=1)


def _convert_pydantic_errors(e: ValidationError) -> list[str]:
    return [f"{err['loc'][0]}: {err['msg']}" for err in e.errors()]


async def registrar_empresa(data: dict) -> dict:
    try:
        validated_data = EmpresaRegistro.model_validate(data)
    except ValidationError as e:
        input_errors = _convert_pydantic_errors(e)
        raise AppValidationError("Datos de registro inválidos", details={"errors": input_errors})

    password_hash = generate_password_hash(validated_data.password)

    exito_db, resultado_db = await user_repository.crear_nueva_empresa(
        validated_data.id_empresa,
        validated_data.nombre_empresa,
        validated_data.email,
        password_hash,
    )

    if exito_db:
        logger.info(f"Empresa registrada: {validated_data.email}, ID: {validated_data.id_empresa}")
        return {
            "mensaje": "Empresa registrada exitosamente.",
            "id_empresa": validated_data.id_empresa,
            "email": validated_data.email,
            "db_info": resultado_db,
        }
    else:
        logger.warning(f"Fallo al registrar empresa: {validated_data.email}. Razón: {resultado_db}")
        if "ya existe" in str(resultado_db):
            raise AppValidationError(f"Error de registro: {resultado_db}")
        raise ServiceError(
            "No se pudo registrar la empresa en la base de datos.", details=resultado_db
        )


async def autenticar_empresa(data: dict) -> str:
    try:
        validated_data = EmpresaLogin.model_validate(data)
    except ValidationError as e:
        raise AppValidationError(
            "Datos de login inválidos", details={"errors": _convert_pydantic_errors(e)}
        )

    usuario_data_db = await user_repository.buscar_empresa_por_email(validated_data.email)

    if usuario_data_db and check_password_hash(
        usuario_data_db["password_hash"], validated_data.password
    ):
        main_identity = str(usuario_data_db["id_empresa"])

        additional_claims_data = {
            "email": str(usuario_data_db["_id"]),
            "nombre_empresa": str(usuario_data_db.get("nombre_empresa", "")),
        }

        access_token = create_access_token(
            identity=main_identity,
            additional_claims=additional_claims_data,
            expires_delta=ACCESS_EXPIRES,
        )

        logger.info(
            f"Empresa autenticada: {validated_data.email}, ID: {usuario_data_db['id_empresa']}"
        )
        return access_token

    logger.warning(f"Fallo de autenticación para: {validated_data.email}")
    raise SecurityError("Credenciales inválidas (email o password incorrectos).")


async def obtener_datos_empresa_por_id(id_empresa: str) -> dict:
    if not id_empresa:
        raise AppValidationError("id_empresa es requerido")

    empresa = await user_repository.buscar_empresa_por_id_empresa(id_empresa)
    if not empresa:
        raise ResourceNotFound(f"Empresa '{id_empresa}' no encontrada")
    return empresa
