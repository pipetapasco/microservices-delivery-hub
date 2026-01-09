"""
Consumer de eventos de despacho de RabbitMQ.

FIX DE CONCURRENCIA:
- Se usa `asyncio.run_coroutine_threadsafe()` para enviar mensajes WebSocket
  desde el hilo del consumidor hacia el Main Event Loop de FastAPI.
- La variable `main_event_loop` se inyecta desde main.py al iniciar.
"""

import asyncio
import json
import time

import pika
from sqlalchemy.orm import Session

from ..core.config import settings
from ..core.logger import get_logger
from ..crud import crud_driver
from ..db.session import SessionLocal
from ..websockets.connection_manager import websocket_connection_manager

logger = get_logger("dispatch_consumer")

main_event_loop: asyncio.AbstractEventLoop | None = None


def set_main_loop(loop: asyncio.AbstractEventLoop):
    """Inyecta el Main Event Loop desde main.py para comunicación thread-safe."""
    global main_event_loop
    main_event_loop = loop
    logger.info("Main Event Loop inyectado en el consumidor de despacho")


def get_db_session_for_consumer() -> Session:
    if not SessionLocal:
        raise RuntimeError("SessionLocal de SQLAlchemy no está inicializada")
    return SessionLocal()


def process_dispatch_event_sync(message_body_str: str):
    """
    Procesa un evento de despacho de forma SÍNCRONA.

    FIX CONCURRENCIA:
    - Las consultas DB se ejecutan síncronamente (OK en hilo secundario)
    - Los envíos WebSocket usan `run_coroutine_threadsafe` para ejecutarse
      en el Main Event Loop de FastAPI
    """
    logger.info("Evento de despacho recibido, procesando...")
    db_session: Session | None = None

    try:
        pedido_data = json.loads(message_body_str)
        id_pedido_str = pedido_data.get("id_pedido")
        tipo_servicio = pedido_data.get("tipo_servicio")
        origen_descripcion = pedido_data.get("origen_descripcion")
        destino_descripcion = pedido_data.get("destino_descripcion")
        nombre_cliente = pedido_data.get("nombre_cliente")

        logger.info(
            f"Pedido ID: {id_pedido_str}, Tipo: {tipo_servicio}, Origen: {origen_descripcion}"
        )

        db_session = get_db_session_for_consumer()
        conductores_aptos_db = crud_driver.get_available_validated_drivers(
            db=db_session, limit=1000
        )
        logger.info(f"Conductores disponibles encontrados: {len(conductores_aptos_db)}")

        if not conductores_aptos_db:
            logger.warning(f"No se encontraron conductores aptos para el pedido: {id_pedido_str}")
            return

        notificacion_payload = {
            "type": "nuevo_servicio_disponible",
            "data": {
                "id_pedido": id_pedido_str,
                "tipo_servicio": tipo_servicio,
                "origen_descripcion": origen_descripcion,
                "destino_descripcion": destino_descripcion,
                "nombre_cliente": nombre_cliente,
                "id_empresa_asociada": pedido_data.get("id_empresa_asociada"),
                "items_pedido": pedido_data.get("items_pedido"),
                "detalles_adicionales_pedido": pedido_data.get("detalles_adicionales_pedido"),
                "metodo_pago_sugerido": pedido_data.get("metodo_pago_sugerido"),
                "monto_estimado_pedido": pedido_data.get("monto_estimado_pedido"),
                "fecha_solicitud_utc": pedido_data.get("fecha_solicitud_utc"),
            },
        }

        if main_event_loop is None:
            logger.error("Main Event Loop no está configurado. No se pueden enviar WebSockets.")
            return

        notificaciones_intentadas = 0
        for conductor_db_obj in conductores_aptos_db:
            conductor_id_uuid = conductor_db_obj.id_conductor
            logger.info(
                f"Notificando al conductor {conductor_id_uuid} sobre pedido {id_pedido_str}"
            )

            asyncio.run_coroutine_threadsafe(
                websocket_connection_manager.send_personal_json(
                    data=notificacion_payload, driver_id=conductor_id_uuid
                ),
                main_event_loop,
            )
            notificaciones_intentadas += 1

        logger.info(
            f"Notificaciones programadas: {notificaciones_intentadas}/{len(conductores_aptos_db)}"
        )

    except json.JSONDecodeError:
        logger.error(f"Mensaje no es JSON válido: {message_body_str[:200]}...")
    except Exception as e:
        logger.exception(f"Error procesando evento de despacho: {e}")
    finally:
        if db_session:
            db_session.close()
            logger.debug("Sesión de DB cerrada")


def on_dispatch_message_callback(channel, method, properties, body):
    """Callback para mensajes de RabbitMQ - llama a función síncrona."""
    message_body_str = body.decode("utf-8")
    logger.info(f"Mensaje de DESPACHO recibido. RK: {method.routing_key}")

    process_dispatch_event_sync(message_body_str)

    channel.basic_ack(delivery_tag=method.delivery_tag)
    logger.debug("Mensaje procesado y ACK enviado")


_dispatch_consumer_connection = None
_dispatch_consumer_channel = None
_dispatch_consumer_tag = None


def start_dispatch_consumer():
    """Inicia el consumidor de eventos de despacho."""
    global _dispatch_consumer_connection, _dispatch_consumer_channel, _dispatch_consumer_tag
    retries = 0
    max_retries = 30

    while retries < max_retries:
        try:
            credentials = pika.PlainCredentials(settings.RABBITMQ_USER, settings.RABBITMQ_PASSWORD)
            parameters = pika.ConnectionParameters(
                host=settings.RABBITMQ_HOST,
                port=settings.RABBITMQ_PORT,
                credentials=credentials,
                heartbeat=600,
                blocked_connection_timeout=300,
            )
            _dispatch_consumer_connection = pika.BlockingConnection(parameters)
            _dispatch_consumer_channel = _dispatch_consumer_connection.channel()
            _dispatch_consumer_channel.exchange_declare(
                exchange=settings.RABBITMQ_DISPATCH_EXCHANGE, exchange_type="direct", durable=True
            )
            result = _dispatch_consumer_channel.queue_declare(
                queue=settings.RABBITMQ_MOTOTAXI_DISPATCH_QUEUE, durable=True
            )
            queue_name = result.method.queue
            _dispatch_consumer_channel.queue_bind(
                exchange=settings.RABBITMQ_DISPATCH_EXCHANGE,
                queue=queue_name,
                routing_key=settings.RABBITMQ_DISPATCH_MOTOTAXI_ROUTING_KEY,
            )
            _dispatch_consumer_tag = _dispatch_consumer_channel.basic_consume(
                queue=queue_name, on_message_callback=on_dispatch_message_callback, auto_ack=False
            )

            logger.info(f"Esperando eventos de despacho en la cola '{queue_name}'")

            _dispatch_consumer_channel.start_consuming()
            break

        except pika.exceptions.AMQPConnectionError as e:
            retries += 1
            if retries >= max_retries:
                logger.error(f"No se pudo conectar a RabbitMQ tras {max_retries} intentos: {e}")
                break

            logger.warning(
                f"Conexión a RabbitMQ falló (intento {retries}/{max_retries}). "
                f"Reintentando en 2s... Error: {e}"
            )
            time.sleep(2)

        except KeyboardInterrupt:
            logger.info("Consumidor de despacho detenido manualmente")
            break
        except Exception as e:
            logger.exception(f"Error inesperado en consumidor de despacho: {e}")
            break
        finally:
            stop_dispatch_consumer()


def stop_dispatch_consumer():
    """Detiene el consumidor de eventos de despacho."""
    global _dispatch_consumer_connection, _dispatch_consumer_channel, _dispatch_consumer_tag
    logger.info("Deteniendo consumidor de despacho...")

    if _dispatch_consumer_channel and _dispatch_consumer_channel.is_open and _dispatch_consumer_tag:
        try:
            _dispatch_consumer_channel.basic_cancel(consumer_tag=_dispatch_consumer_tag)
        except Exception as e:
            logger.error(f"Error cancelando consumo: {e}")

    if _dispatch_consumer_channel and _dispatch_consumer_channel.is_open:
        try:
            _dispatch_consumer_channel.close()
        except Exception as e:
            logger.error(f"Error cerrando canal: {e}")

    if _dispatch_consumer_connection and _dispatch_consumer_connection.is_open:
        try:
            _dispatch_consumer_connection.close()
        except Exception as e:
            logger.error(f"Error cerrando conexión: {e}")

    _dispatch_consumer_channel = None
    _dispatch_consumer_connection = None
    _dispatch_consumer_tag = None
    logger.info("Consumidor de despacho detenido")
