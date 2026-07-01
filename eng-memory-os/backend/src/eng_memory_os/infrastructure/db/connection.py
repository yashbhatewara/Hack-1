"""
Async database connection pool management.

Manages SQLAlchemy async engine and session factory lifecycle.
Used by the FastAPI lifespan and background worker for connection pooling.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

import structlog

logger = structlog.get_logger(__name__)


class DatabaseSessionManager:
    """Manages the async database engine and session factory.

    Usage:
        manager = DatabaseSessionManager(database_url)
        await manager.initialize()

        async with manager.session() as session:
            result = await session.execute(...)

        await manager.close()
    """

    def __init__(self, database_url: str) -> None:
        self._database_url = database_url
        self._engine: AsyncEngine | None = None
        self._session_factory: async_sessionmaker[AsyncSession] | None = None

    async def initialize(self) -> None:
        """Create the async engine and session factory."""
        self._engine = create_async_engine(
            self._database_url,
            echo=False,
            pool_size=20,
            max_overflow=10,
            pool_pre_ping=True,
            pool_recycle=3600,
        )
        self._session_factory = async_sessionmaker(
            bind=self._engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )
        logger.info(
            "database_initialized",
            url=self._database_url.split("@")[-1],  # Log host only, not credentials
        )

    async def close(self) -> None:
        """Dispose of the engine and release all connections."""
        if self._engine:
            await self._engine.dispose()
            logger.info("database_closed")

    @asynccontextmanager
    async def session(self) -> AsyncGenerator[AsyncSession, None]:
        """Provide a transactional session scope.

        Commits on success, rolls back on exception.
        """
        if self._session_factory is None:
            raise RuntimeError("DatabaseSessionManager is not initialized. Call initialize() first.")

        session = self._session_factory()
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

    @property
    def engine(self) -> AsyncEngine:
        if self._engine is None:
            raise RuntimeError("DatabaseSessionManager is not initialized.")
        return self._engine
