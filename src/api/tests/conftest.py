"""Shared pytest fixtures for the certsapi test suite."""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime

import pytest
import pytest_asyncio
from ctpool.models import Base, Certificate, CtLogSource, Hostname
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from certsapi.app import create_app
from certsapi.config import Settings

_TEST_DB_URL = "postgresql+psycopg://ctpool:ctpool@localhost:5432/ctpool_test"

# Credential-free Settings used by all unit tests that call create_app().
# PostgresDsn requires a valid URL structure but no password is needed.
_UNIT_TEST_SETTINGS = Settings.model_validate(
    {"database_url": "postgresql+psycopg://localhost/test"}
)


@pytest_asyncio.fixture(scope="session")
async def async_engine() -> AsyncGenerator[AsyncEngine, None]:
    """Async engine connected to ctpool_test; creates/drops schema once per session."""
    engine = create_async_engine(_TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture()
async def db_session(async_engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    """AsyncSession wrapped in a savepoint; rolls back after each test."""
    factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
        async_engine, expire_on_commit=False
    )
    async with factory() as session:
        async with session.begin():
            async with session.begin_nested():
                yield session
            await session.rollback()


@pytest.fixture()
def app() -> object:
    """Bare FastAPI app instance for dependency override testing."""
    return create_app(settings=_UNIT_TEST_SETTINGS)


@pytest_asyncio.fixture()
async def http_client(app: object) -> AsyncGenerator[AsyncClient, None]:
    """AsyncClient backed by the ASGI transport — no real network."""
    async with AsyncClient(
        transport=ASGITransport(app=app),  # type: ignore[arg-type]
        base_url="http://test",
    ) as client:
        yield client


# ---------------------------------------------------------------------------
# ORM factory helpers used by integration tests
# ---------------------------------------------------------------------------


def make_log_source(**kwargs: object) -> CtLogSource:
    """Return an unsaved CtLogSource with sensible defaults."""
    defaults: dict[str, object] = {
        "log_id_b64": str(uuid.uuid4()),
        "operator_name": "Test Operator",
        "description": "Test Log",
        "url": f"https://ct.test/{uuid.uuid4().hex}/",
        "public_key_b64": "dGVzdA==",
        "log_state": "usable",
        "source_list": "google",
        "is_eligible_for_tail": True,
        "is_eligible_for_backfill": True,
    }
    defaults.update(kwargs)
    return CtLogSource(**defaults)  # type: ignore[arg-type]


def make_certificate(**kwargs: object) -> Certificate:
    """Return an unsaved Certificate with sensible defaults."""
    fp = uuid.uuid4().hex
    now = datetime.now(UTC)
    defaults: dict[str, object] = {
        "fingerprint_sha256": fp,
        "spki_sha256": fp,
        "serial_number": "01",
        "issuer_dn": "CN=Test CA",
        "subject_dn": "CN=test.example.com",
        "not_before": now,
        "not_after": now,
        "signature_algorithm_oid": "1.2.840.113549.1.1.11",
        "signature_algorithm_name": "sha256WithRSAEncryption",
        "public_key_algorithm_oid": "1.2.840.113549.1.1.1",
        "public_key_algorithm_name": "rsaEncryption",
        "is_precertificate": False,
        "is_wildcard_present": False,
        "san_count": 1,
    }
    defaults.update(kwargs)
    return Certificate(**defaults)  # type: ignore[arg-type]


def make_hostname(**kwargs: object) -> Hostname:
    """Return an unsaved Hostname with sensible defaults."""
    name = f"sub-{uuid.uuid4().hex[:8]}.example.com"
    defaults: dict[str, object] = {
        "hostname": name,
        "registrable_domain": "example.com",
        "is_wildcard": False,
    }
    defaults.update(kwargs)
    return Hostname(**defaults)  # type: ignore[arg-type]
