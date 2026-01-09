import threading
import uuid

from fastapi import WebSocket

from ..core.logger import get_logger

logger = get_logger("connection_manager")


class ConnectionManager:
    """Gestor de conexiones WebSocket thread-safe para conductores."""

    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}
        self._lock = threading.Lock()
        logger.info("Gestor de conexiones WebSocket inicializado")

    async def connect(self, websocket: WebSocket, driver_id: uuid.UUID):
        """Acepta una nueva conexión WebSocket y la registra."""
        await websocket.accept()
        driver_id_str = str(driver_id)
        with self._lock:
            self.active_connections[driver_id_str] = websocket
            connection_count = len(self.active_connections)
        logger.info(f"Conductor {driver_id_str} conectado. Conexiones activas: {connection_count}")

    def disconnect(self, driver_id: uuid.UUID):
        """Desconecta y elimina una conexión WebSocket."""
        driver_id_str = str(driver_id)
        with self._lock:
            removed = self.active_connections.pop(driver_id_str, None)
            connection_count = len(self.active_connections)
        if removed:
            logger.info(
                f"Conductor {driver_id_str} desconectado. Conexiones activas: {connection_count}"
            )
        else:
            logger.warning(f"Intento de desconectar conductor {driver_id_str} no encontrado")

    async def get_connection(self, driver_id: uuid.UUID) -> WebSocket | None:
        """Obtiene la conexión WebSocket activa para un driver_id."""
        driver_id_str = str(driver_id)
        with self._lock:
            return self.active_connections.get(driver_id_str)

    async def send_personal_message(self, message: str, driver_id: uuid.UUID):
        """Envía un mensaje de texto a un conductor específico."""
        driver_id_str = str(driver_id)
        with self._lock:
            websocket = self.active_connections.get(driver_id_str)

        if websocket:
            try:
                await websocket.send_text(message)
                logger.info(f"Mensaje enviado a conductor {driver_id_str}: {message[:70]}...")
            except Exception as e:
                logger.error(f"Error enviando mensaje a conductor {driver_id_str}: {e}")
                self.disconnect(driver_id)
        else:
            logger.warning(f"No hay conexión activa para conductor {driver_id_str}")

    async def send_personal_json(self, data: dict, driver_id: uuid.UUID):
        """Envía datos JSON a un conductor específico."""
        driver_id_str = str(driver_id)
        with self._lock:
            websocket = self.active_connections.get(driver_id_str)

        if websocket:
            try:
                await websocket.send_json(data)
                logger.info(f"JSON enviado a conductor {driver_id_str}: {str(data)[:70]}...")
            except Exception as e:
                logger.error(f"Error enviando JSON a conductor {driver_id_str}: {e}")
                self.disconnect(driver_id)
        else:
            logger.warning(f"No hay conexión activa para conductor {driver_id_str}")


websocket_connection_manager = ConnectionManager()
