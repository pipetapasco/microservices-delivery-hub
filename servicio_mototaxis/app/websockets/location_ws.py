import json
import uuid

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect, status
from jose import JWTError, jwt
from pydantic import ValidationError

from ..core.config import settings
from ..core.logger import get_logger
from ..models.location_models import LocationData
from ..services import location_service
from .connection_manager import websocket_connection_manager

logger = get_logger("location_ws")

router = APIRouter(
    tags=["WebSockets - Location"],
)


async def get_driver_id_from_token_ws(token: str | None = None) -> uuid.UUID:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No se pudieron validar las credenciales del token para WebSocket",
    )
    if token is None:
        logger.warning("Token no proporcionado en conexión WebSocket")
        raise credentials_exception
    try:
        payload = jwt.decode(
            token, settings.JWT_SECRET_KEY_MOTOTAXIS, algorithms=[settings.JWT_ALGORITHM]
        )
        id_conductor_str: str | None = payload.get("sub")
        if id_conductor_str is None:
            logger.warning("id_conductor (sub) no encontrado en el payload del token")
            raise credentials_exception
        try:
            id_conductor_uuid = uuid.UUID(id_conductor_str)
            logger.debug(f"Token validado para conductor ID: {id_conductor_uuid}")
            return id_conductor_uuid
        except ValueError:
            logger.warning(f"id_conductor '{id_conductor_str}' en token no es UUID válido")
            raise credentials_exception
    except JWTError as e:
        logger.warning(f"Error decodificando JWT: {e}")
        raise credentials_exception


@router.websocket("/ws/drivers/location")
async def websocket_location_endpoint(websocket: WebSocket, token: str | None = None):
    driver_id: uuid.UUID | None = None
    try:
        if not token:
            logger.warning("Conexión WebSocket rechazada: Token no proporcionado en query params")
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

        driver_id = await get_driver_id_from_token_ws(token=token)

        await websocket_connection_manager.connect(websocket, driver_id)

        await websocket_connection_manager.send_personal_json(
            {"type": "connection_ack", "message": "Conectado al servidor de ubicación."}, driver_id
        )

        while True:
            try:
                data_str = await websocket.receive_text()
                logger.debug(f"Mensaje de ubicación recibido de {driver_id}")

                try:
                    location_payload = json.loads(data_str)
                    location_data = LocationData(**location_payload)
                except json.JSONDecodeError:
                    logger.warning(f"Mensaje de {driver_id} no es JSON válido")
                    await websocket_connection_manager.send_personal_json(
                        {"type": "error", "message": "Mensaje no es JSON válido."}, driver_id
                    )
                    continue
                except ValidationError as e:
                    logger.warning(f"Datos de ubicación inválidos de {driver_id}: {e.errors()}")
                    await websocket_connection_manager.send_personal_json(
                        {"type": "error", "message": f"Datos de ubicación inválidos: {e.errors()}"},
                        driver_id,
                    )
                    continue

                success = await location_service.update_driver_realtime_location(
                    driver_id=driver_id, location_data=location_data
                )

                if success:
                    logger.debug(f"Ubicación de {driver_id} procesada correctamente")
                else:
                    logger.warning(f"Fallo al procesar ubicación de {driver_id}")

            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error(
                    f"Error inesperado en bucle para conductor ID {driver_id}: {e}", exc_info=True
                )
                try:
                    await websocket_connection_manager.send_personal_json(
                        {"type": "error", "message": "Error interno del servidor"}, driver_id
                    )
                except Exception as send_error:
                    logger.debug(f"No se pudo enviar mensaje de error al cliente: {send_error}")

    except HTTPException as http_auth_exc:
        logger.warning(f"Fallo de autenticación al conectar: {http_auth_exc.detail}")
    except Exception as e:
        logger.error(
            f"Error general al establecer conexión para driver_id {driver_id if driver_id else 'desconocido'}: {e}",
            exc_info=True,
        )
    finally:
        if driver_id:
            websocket_connection_manager.disconnect(driver_id)
            logger.info(f"Conductor ID {driver_id} desconectado y eliminado del gestor")
