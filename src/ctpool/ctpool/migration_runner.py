"""Programmatic Alembic migration runner.

Exports:
    run_upgrade_head     — Apply all pending migrations to the target database.
    get_current_revision — Return the current Alembic revision string (or None).
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from alembic import command as alembic_command
from alembic.config import Config as AlembicConfig
from alembic.runtime.migration import MigrationContext
from sqlalchemy import Connection, create_engine, text

from ctpool.config import Settings

# Path to the alembic.ini co-located with this package root
_ALEMBIC_INI = Path(__file__).parent.parent / "alembic.ini"


def _make_alembic_cfg(settings: Settings) -> AlembicConfig:
    """Build an AlembicConfig pointing at the project alembic.ini."""
    cfg = AlembicConfig(str(_ALEMBIC_INI))
    cfg.set_main_option("sqlalchemy.url", str(settings.database_url))
    return cfg


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
