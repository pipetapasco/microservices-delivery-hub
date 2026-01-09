from pathlib import Path

from pydantic import computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict

from .logger import get_logger

logger = get_logger("config")

BASE_DIR = Path(__file__).resolve().parent.parent.parent
ENV_PATH = BASE_DIR / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ENV_PATH, env_file_encoding="utf-8", case_sensitive=True, extra="ignore"
    )

    PROJECT_NAME: str = "Servicio de Mototaxis"
    API_V1_STR: str = "/api/v1"
    MOTOTAXIS_SERVICE_PORT: int = 5002
    DEBUG: bool = False

    JWT_SECRET_KEY_MOTOTAXIS: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    POSTGRES_SERVER: str = "localhost"
    POSTGRES_PORT: int = 5433
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str = "mototaxis_db"

    @computed_field
    def DATABASE_URL(self) -> str:
        return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: str | None = None
    REDIS_DB: int = 0
    REDIS_DRIVER_LOCATIONS_KEY: str = "driver_locations"

    RABBITMQ_HOST: str = "localhost"
    RABBITMQ_PORT: int = 5672
    RABBITMQ_USER: str = "guest"
    RABBITMQ_PASSWORD: str = ""
    RABBITMQ_DISPATCH_EXCHANGE: str = "dispatch_exchange"
    RABBITMQ_MOTOTAXI_DISPATCH_QUEUE: str = "cola_despacho_mototaxis"
    RABBITMQ_DISPATCH_MOTOTAXI_ROUTING_KEY: str = "pedido.requiere_mototaxi"
    RABBITMQ_ORDER_UPDATE_ROUTING_KEY: str = "pedido.conductor_acepto"


settings = Settings()

logger.info(f"Servicio Mototaxis configurado - Puerto: {settings.MOTOTAXIS_SERVICE_PORT}")
