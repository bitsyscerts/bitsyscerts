"""Programmatic Alembic migration runner.

Exports:
    run_upgrade_head     — Apply all pending migrations to the target database.
    get_current_revision — Return the current Alembic revision string (or None).
    get_missing_core_tables — Return core tables expected but absent.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from alembic import command as alembic_command
from alembic.config import Config as AlembicConfig
from alembic.runtime.migration import MigrationContext
from sqlalchemy import Connection, create_engine, text

from ctpool.config import Settings
from ctpool.exceptions import SchemaStateError

_PACKAGED_MIGRATIONS = Path(__file__).resolve().parent / "_alembic" / "migrations"
_SOURCE_MIGRATIONS = Path(__file__).resolve().parent.parent / "migrations"
_DOCKER_MIGRATIONS = Path("/app/migrations")
_CORE_TABLES = (
    "certificates",
    "certificate_hostnames",
    "ct_log_backfill_ranges",
    "ct_log_observations",
    "ct_log_runtime_state",
    "ct_log_sources",
    "ct_log_tail_cursors",
    "hostnames",
    "ingestion_errors",
    "ingestion_metrics",
)


def _make_alembic_cfg(settings: Settings) -> AlembicConfig:
    """Build an AlembicConfig pointing at the resolved migration directory."""
    cfg = AlembicConfig()
    cfg.set_main_option("script_location", str(_resolve_migration_root()))
    cfg.set_main_option("sqlalchemy.url", str(settings.database_url))
    return cfg


def _resolve_migration_root() -> Path:
    """Return the migration-script directory for source, wheel, or container
    installs.
    """
    for candidate in (_PACKAGED_MIGRATIONS, _SOURCE_MIGRATIONS, _DOCKER_MIGRATIONS):
        if candidate.is_dir():
            return candidate

    raise SchemaStateError(
        "Alembic migration scripts were not found. Expected a migrations directory "
        "in the installed ctpool package, the source tree, or /app/migrations."
    )


def _upgrade_sync(cfg: AlembicConfig) -> None:
    """Run alembic upgrade head synchronously (called from executor)."""
    alembic_command.upgrade(cfg, "head")


def _get_revision_sync(connection: Connection) -> str | None:
    """Return current Alembic revision from a synchronous connection."""
    ctx = MigrationContext.configure(connection)
    return ctx.get_current_revision()


def _fetch_revision_sync(url: str) -> str | None:
    """Open a synchronous connection and return the Alembic revision.

    Uses the psycopg sync driver (``postgresql+psycopg://…``).
    Returns ``None`` if the ``alembic_version`` table does not exist.
    """
    engine = create_engine(url)
    with engine.connect() as conn:
        result = conn.execute(
            text("SELECT to_regclass('public.alembic_version') IS NOT NULL")
        )
        exists: bool = result.scalar_one()
        if not exists:
            return None
        return _get_revision_sync(conn)


def _fetch_public_tables_sync(url: str) -> set[str]:
    """Return the set of public table names present in the target database."""
    engine = create_engine(url)
    with engine.connect() as conn:
        result = conn.execute(
            text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
        )
        return {str(row[0]) for row in result}


def _missing_core_tables(url: str) -> tuple[str, ...]:
    """Return the required core tables absent from the target database."""
    present_tables = _fetch_public_tables_sync(url)
    return tuple(table for table in _CORE_TABLES if table not in present_tables)


def _raise_for_incomplete_schema(url: str) -> None:
    """Raise when Alembic revision state exists but required tables are absent."""
    missing_tables = _missing_core_tables(url)
    if not missing_tables:
        return
    missing_list = ", ".join(missing_tables)
    raise SchemaStateError(
        "Database revision is marked as migrated, but required tables are "
        f"missing: {missing_list}."
    )


async def run_upgrade_head(settings: Settings) -> None:
    """Apply all pending Alembic migrations to the target database.

    Runs in a thread-pool executor because Alembic uses synchronous
    SQLAlchemy internally.

    Args:
        settings: Application settings containing the database URL.
    """
    cfg = _make_alembic_cfg(settings)
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, _upgrade_sync, cfg)
    await loop.run_in_executor(
        None,
        _raise_for_incomplete_schema,
        str(settings.database_url),
    )


async def get_current_revision(settings: Settings) -> str | None:
    """Return the current Alembic revision or None if no migrations applied.

    Args:
        settings: Application settings containing the database URL.

    Returns:
        The current revision string (e.g., ``"a1b2c3d4e5f6"``) or ``None``.
    """
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        None, _fetch_revision_sync, str(settings.database_url)
    )


async def get_missing_core_tables(settings: Settings) -> tuple[str, ...]:
    """Return core application tables that are missing from the target DB."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        None, _missing_core_tables, str(settings.database_url)
    )
