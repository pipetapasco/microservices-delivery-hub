import redis
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from ..core.config import settings
from ..core.logger import get_logger

logger = get_logger("session")

SQLALCHEMY_DATABASE_URL = settings.DATABASE_URL
engine = None
SessionLocal = None

if SQLALCHEMY_DATABASE_URL:
    engine = create_engine(SQLALCHEMY_DATABASE_URL, pool_pre_ping=True, echo=False)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    logger.info(
        f"Motor SQLAlchemy creado para PostgreSQL en {settings.POSTGRES_SERVER}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}"
    )
else:
    logger.error(
        "SQLALCHEMY_DATABASE_URL no está configurada. El motor de base de datos no se pudo crear."
    )

Base = declarative_base()


def get_db():
    if SessionLocal is None:
        raise RuntimeError("La sesión de base de datos (SessionLocal) no está inicializada.")
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    if engine is None:
        logger.error(
            "El motor de base de datos no está inicializado. No se pueden crear las tablas."
        )
        return
    try:
        logger.info("Intentando crear tablas en la base de datos (si no existen)...")
        Base.metadata.create_all(bind=engine)
        logger.info("Tablas verificadas/creadas.")
    except Exception as e:
        logger.error(f"Error al intentar crear las tablas: {e}", exc_info=True)


redis_client = None


def get_redis_client():
    """
    Crea y devuelve una instancia del cliente de Redis.
    La conexión se crea una vez y se reutiliza.
    """
    global redis_client
    if redis_client is None:
        try:
            logger.info(
                f"Intentando conectar a Redis: Host={settings.REDIS_HOST}, Puerto={settings.REDIS_PORT}, DB={settings.REDIS_DB}"
            )
            redis_client = redis.Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                db=settings.REDIS_DB,
                password=settings.REDIS_PASSWORD if settings.REDIS_PASSWORD else None,
                decode_responses=True,
            )
            redis_client.ping()
            logger.info("Conexión a Redis establecida exitosamente.")
        except redis.exceptions.ConnectionError as e:
            logger.error(f"No se pudo conectar a Redis: {e}", exc_info=True)
            redis_client = None
        except Exception as e:
            logger.error(f"Error inesperado al configurar el cliente de Redis: {e}", exc_info=True)
            redis_client = None

    if redis_client is None:
        logger.warning(
            "El cliente de Redis no está inicializado. Las operaciones de Redis fallarán."
        )

    return redis_client
