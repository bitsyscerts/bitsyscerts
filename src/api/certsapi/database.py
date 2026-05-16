"""Async SQLAlchemy engine factory and per-request session dependency."""

from __future__ import annotations

import functools
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from certsapi.config import get_settings


@functools.lru_cache(maxsize=1)
def _get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Build and cache the async session factory from application settings."""
    settings = get_settings()
    engine = create_async_engine(
        str(settings.database_url),
        pool_pre_ping=True,
        echo=False,
        connect_args={"options": "-c statement_timeout=30000"},
    )
    return async_sessionmaker(engine, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield an AsyncSession scoped to the current request.

    Commits on success, rolls back on exception, and always closes the
    session when the request context exits.
    """
    async with _get_session_factory()() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
