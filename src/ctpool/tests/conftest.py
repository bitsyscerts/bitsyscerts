"""Shared pytest fixtures for the ctpool test suite."""

from __future__ import annotations

import os
import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from ctpool.config import Settings
from ctpool.models import Base, CtLogSource
from ctpool.test_database_url import TEST_DATABASE_URL_ENV, resolve_test_database_url

_DEFAULT_TEST_DB = "postgresql+psycopg://ctpool:ctpool@localhost:5432/ctpool_test"


@pytest.fixture()
def test_settings() -> Settings:
    """Settings pointing at the integration-test database.

    Prefers ``BITSYSCERTS_TEST_DATABASE_URL`` when present. Otherwise derives a
    sibling ``*_test`` database from ``DATABASE_URL`` so test teardown never
    targets the live development database by accident.
    """
    db_url = resolve_test_database_url(
        source_database_url=os.environ.get("DATABASE_URL"),
        explicit_test_database_url=os.environ.get(TEST_DATABASE_URL_ENV),
        fallback_database_url=_DEFAULT_TEST_DB,
    )
    return Settings.model_validate({"database_url": db_url})


@pytest_asyncio.fixture()
async def async_engine(
    test_settings: Settings,
) -> AsyncGenerator[AsyncEngine, None]:
    """Async SQLAlchemy engine connected to a freshly recreated test schema."""
    engine = create_async_engine(str(test_settings.database_url), echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture()
async def db_session(
    async_engine: AsyncEngine,
) -> AsyncGenerator[AsyncSession, None]:
    """AsyncSession wrapped in a savepoint; rolls back after each test."""
    factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
        async_engine,
        expire_on_commit=False,
    )
    async with factory() as session:
        async with session.begin():
            async with session.begin_nested():
                yield session
            await session.rollback()


@pytest.fixture()
def mock_httpx_client() -> AsyncMock:
    """Async mock of httpx.AsyncClient."""
    return AsyncMock()


@pytest.fixture()
def worker_id() -> str:
    """Consistent worker identity string for tests."""
    return "test-host:12345"


@pytest.fixture()
def ct_log_source_factory() -> object:
    """Factory callable returning a CtLogSource with sensible defaults."""

    def _factory(**kwargs: object) -> CtLogSource:
        defaults: dict[str, object] = {
            "id": uuid.uuid4(),
            "log_id_b64": "dGVzdA==",
            "operator_name": "Test Operator",
            "description": "Test CT Log",
            "url": "https://ct.example.com/log/",
            "public_key_b64": "dGVzdGtleQ==",
            "log_state": "usable",
            "is_eligible_for_tail": True,
            "is_eligible_for_backfill": True,
            "source_list": "chrome",
            "first_seen_at": datetime.now(UTC),
            "last_synced_at": datetime.now(UTC),
        }
        defaults.update(kwargs)
        return CtLogSource(**defaults)

    return _factory
