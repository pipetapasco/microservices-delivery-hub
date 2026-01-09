# servicio_pedidos/app/db/session.py
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base

from ..core.config import settings
from ..core.logging_config import get_logger

logger = get_logger(__name__)

Base = declarative_base()

# Build async database URL (postgresql+asyncpg://) - Now from settings
ASYNC_DATABASE_URL = settings.ASYNC_DATABASE_URL

async_engine = None
AsyncSessionLocal = None

if ASYNC_DATABASE_URL:
    async_engine = create_async_engine(
        ASYNC_DATABASE_URL, pool_pre_ping=True, echo=False, pool_size=5, max_overflow=10
    )
    AsyncSessionLocal = async_sessionmaker(
        bind=async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )

    safe_url = (
        ASYNC_DATABASE_URL.replace(settings.POSTGRES_PASSWORD, "********")
        if settings.POSTGRES_PASSWORD
        else ASYNC_DATABASE_URL
    )
    logger.info(f"Async SQLAlchemy engine created for: {safe_url}")
else:
    logger.error("CRITICAL: DATABASE_URL not configured. Async engine could not be created.")


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency that provides an async database session."""
    if AsyncSessionLocal is None:
        raise RuntimeError("Async database session is not initialized. Check DATABASE_URL.")

    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db_pedidos():
    """Initialize database tables asynchronously."""
    if async_engine is None:
        logger.error("CRITICAL: Async engine not initialized. Cannot create tables.")
        return

    try:
        logger.info("Attempting to create database tables (if not exist)...")
        async with async_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Tables verified/created successfully.")
    except Exception as e:
        logger.exception(f"Error creating database tables: {e}")
