"""
Async SQLAlchemy engine + session factory.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from bot.config import settings

from sqlalchemy.pool import NullPool

engine: AsyncEngine = create_async_engine(
    settings.database_url,
    echo=False,
    connect_args={"ssl": False} if "postgresql" in settings.database_url else {},
    poolclass=NullPool,
)

AsyncSessionFactory: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency that yields a DB session and guarantees cleanup."""
    async with AsyncSessionFactory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
