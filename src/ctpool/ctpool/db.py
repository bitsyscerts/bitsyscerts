"""Async SQLAlchemy engine and session factory construction.

Exports:
    create_engine       — Build an AsyncEngine from Settings.
    create_session_factory — Build an async_sessionmaker from an engine.
    get_session         — Context-manager for a single scoped AsyncSession.
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

from ctpool.config import Settings


def create_engine(settings: Settings) -> AsyncEngine:
    """Return an AsyncEngine configured from *settings*.

    The engine uses ``pool_pre_ping=True`` so stale connections are discarded
    before use, which prevents spurious errors after container restarts.
    """
    return create_async_engine(
        str(settings.database_url),
        pool_pre_ping=True,
        echo=False,
    )


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Return a session factory bound to *engine*.

    ``expire_on_commit=False`` avoids lazy-load errors after a transaction
    commits — required when session objects are returned to callers outside
    the session context.
    """
    return async_sessionmaker(engine, expire_on_commit=False)


@asynccontextmanager
async def get_session(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[AsyncSession, None]:
    """Yield a single :class:`AsyncSession` and commit or roll back on exit.

    Usage::

        async with get_session(factory) as session:
            result = await session.execute(...)

    The session is automatically closed when the context exits regardless of
    whether an exception occurred.
    """
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
