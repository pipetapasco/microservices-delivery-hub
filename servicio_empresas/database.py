import logging

from config import app_config
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorCollection, AsyncIOMotorDatabase

logger = logging.getLogger(__name__)

_mongo_client: AsyncIOMotorClient | None = None
_database: AsyncIOMotorDatabase | None = None
_indexes_initialized: bool = False


def get_mongo_client() -> AsyncIOMotorClient:
    global _mongo_client
    if _mongo_client is None:
        mongo_uri = app_config.MONGO_URI
        if not mongo_uri:
            raise ValueError("MONGO_URI no está configurado.")
        logger.info(f"Conectando a MongoDB (async): {mongo_uri}")
        _mongo_client = AsyncIOMotorClient(mongo_uri)
        logger.info("Cliente Motor (async) inicializado.")
    return _mongo_client


def get_database() -> AsyncIOMotorDatabase:
    global _database
    if _database is None:
        client = get_mongo_client()
        db_name = app_config.MONGO_DB_NAME
        if not db_name:
            raise ValueError("MONGO_DB_NAME no está configurado.")
        _database = client[db_name]
        logger.info(f"Base de datos '{db_name}' obtenida.")
    return _database


def get_collection(collection_name: str) -> AsyncIOMotorCollection:
    db = get_database()
    return db[collection_name]


def get_users_collection() -> AsyncIOMotorCollection:
    collection_name = app_config.MONGO_USERS_COLLECTION
    if not collection_name:
        raise ValueError("MONGO_USERS_COLLECTION no está configurado.")
    return get_collection(collection_name)


def get_menus_collection() -> AsyncIOMotorCollection:
    collection_name = app_config.MONGO_MENUS_COLLECTION
    if not collection_name:
        raise ValueError("MONGO_MENUS_COLLECTION no está configurado.")
    return get_collection(collection_name)


async def init_db_indexes() -> None:
    global _indexes_initialized
    if _indexes_initialized:
        logger.debug("Índices ya inicializados, saltando...")
        return

    logger.info("Inicializando índices de MongoDB...")

    try:
        users_collection = get_users_collection()
        await users_collection.create_index("id_empresa", unique=True)
        await users_collection.create_index("api_keys.key_id", unique=False)
        logger.info("Índices de usuarios creados.")

        menus_collection = get_menus_collection()
        await menus_collection.create_index("id_empresa", unique=True)
        logger.info("Índices de menús creados.")

        _indexes_initialized = True
        logger.info("Todos los índices de MongoDB inicializados correctamente.")
    except Exception as e:
        logger.error(f"Error inicializando índices de MongoDB: {e}", exc_info=True)
        raise


async def close_connection() -> None:
    global _mongo_client, _database, _indexes_initialized
    if _mongo_client is not None:
        _mongo_client.close()
        _mongo_client = None
        _database = None
        _indexes_initialized = False
        logger.info("Conexión a MongoDB cerrada.")
