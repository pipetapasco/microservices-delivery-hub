import logging
import os

from dotenv import load_dotenv

logger = logging.getLogger(__name__)

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
ENV_PATH = os.path.join(BASE_DIR, ".env")

if os.path.exists(ENV_PATH):
    logger.info(f"Cargando variables de entorno desde: {ENV_PATH}")
    load_dotenv(ENV_PATH)
else:
    logger.warning("No se encontró el archivo .env, usando variables de entorno del sistema.")


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY")
    if not SECRET_KEY:
        raise ValueError("SECRET_KEY es requerida. Configúrala en .env")

    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY")
    if not JWT_SECRET_KEY:
        raise ValueError("JWT_SECRET_KEY es requerida. Configúrala en .env")

    DEBUG = os.environ.get("FLASK_DEBUG", "False").lower() == "true"
    MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017/")
    MONGO_DB_NAME = os.environ.get("MONGO_DB_NAME", "db_empresas")
    MONGO_MENUS_COLLECTION = os.environ.get("MONGO_MENUS_COLLECTION", "menus")
    MONGO_USERS_COLLECTION = os.environ.get("MONGO_USERS_COLLECTION", "usuarios_empresas")

    SERVICIO_EMPRESAS_PORT = int(os.environ.get("SERVICIO_EMPRESAS_PORT", 5001))
    TEMP_UPLOADS_FOLDER = os.path.join(BASE_DIR, "temp_uploads")


app_config = Config()
