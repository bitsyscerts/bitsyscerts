"""Tests for ctpool.db — engine/session-factory construction and get_session."""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from ctpool.config import Settings
from ctpool.db import create_engine, create_session_factory, get_session
from ctpool.models import Base

pytestmark = pytest.mark.integration


@pytest.fixture()
def settings(test_settings: Settings) -> Settings:
    """Re-export the shared test_settings fixture under a local name."""
    return test_settings


def test_create_engine_returns_async_engine(settings: Settings) -> None:
    """create_engine() returns an AsyncEngine instance."""
    engine = create_engine(settings)
    assert isinstance(engine, AsyncEngine)


def test_create_engine_url_matches_settings(settings: Settings) -> None:
    """The engine URL reflects the database_url from settings."""
    engine = create_engine(settings)
    # engine.url.database is the DB name; settings.database_url contains it too
    assert engine.url.database in str(settings.database_url)


def test_create_session_factory_returns_sessionmaker(settings: Settings) -> None:
    """create_session_factory() returns an async_sessionmaker."""
    engine = create_engine(settings)
    factory = create_session_factory(engine)
    assert isinstance(factory, async_sessionmaker)


async def test_get_session_yields_async_session(settings: Settings) -> None:
    """get_session() context manager yields an AsyncSession."""
    engine = create_engine(settings)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = create_session_factory(engine)
    async with get_session(factory) as session:
        assert isinstance(session, AsyncSession)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


async def test_get_session_executes_simple_query(settings: Settings) -> None:
    """A session from get_session() can execute a simple SQL query."""
    engine = create_engine(settings)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = create_session_factory(engine)
    async with get_session(factory) as session:
        result = await session.execute(text("SELECT 1"))
        value = result.scalar_one()
        assert value == 1

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


async def test_get_session_rolls_back_on_exception(settings: Settings) -> None:
    """get_session() rolls back the transaction when an exception is raised."""
    engine = create_engine(settings)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = create_session_factory(engine)
    with pytest.raises(ValueError, match="intentional"):
        async with get_session(factory) as _session:
            raise ValueError("intentional")

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


async def test_get_session_commits_on_clean_exit(settings: Settings) -> None:
    """get_session() commits when the context exits without an exception."""
    from datetime import UTC, datetime

    from ctpool.models.log_source import CtLogSource

    engine = create_engine(settings)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = create_session_factory(engine)
    source = CtLogSource(
        log_id_b64="dGVzdA==",
        operator_name="Op",
        description="Test",
        url="https://ct.example.com/test-commit/",
        public_key_b64="a2V5",
        log_state="usable",
        is_eligible_for_tail=False,
        is_eligible_for_backfill=False,
        source_list="chrome",
        first_seen_at=datetime.now(UTC),
        last_synced_at=datetime.now(UTC),
    )
    async with get_session(factory) as session:
        session.add(source)

    # Verify the row persisted
    async with get_session(factory) as session:
        result = await session.execute(
            text("SELECT COUNT(*) FROM ct_log_sources WHERE url = :url"),
            {"url": "https://ct.example.com/test-commit/"},
        )
        count = result.scalar_one()
    assert count == 1

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()
