from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from backend.app.core.config import settings
from backend.app.core.logging import logger
from backend.app.db.base import Base

# Build async engine
engine_kwargs = {
    "echo": False,
    "future": True,
}

# Add pool options for PostgreSQL
if "postgresql" in settings.DATABASE_URL:
    engine_kwargs.update({
        "pool_size": 10,
        "max_overflow": 20,
        "pool_pre_ping": True,
    })

engine: AsyncEngine = create_async_engine(
    settings.DATABASE_URL,
    **engine_kwargs,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for providing database sessions."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """Initialize database tables for local testing and standalone verification."""
    logger.info("Initializing database schema...")
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database schema initialized successfully.", extra={"subsystem": "postgresql", "status": "available"})
    except Exception as exc:
        logger.error("Database initialization failed; API will start in degraded mode.", extra={"subsystem": "postgresql", "status": "unavailable", "error_type": type(exc).__name__})


async def check_db_health() -> bool:
    """Probe the configured database without making API liveness depend on it."""
    from sqlalchemy import text

    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
        return True
    except Exception as exc:
        logger.warning("Database health probe failed.", extra={"subsystem": "postgresql", "status": "unavailable", "error_type": type(exc).__name__})
        return False
