"""Alembic migration environment — async SQLAlchemy with explicit model imports."""

from __future__ import annotations

import asyncio
from logging.config import fileConfig
from typing import Any

from alembic import context
from sqlalchemy.ext.asyncio import async_engine_from_config
from sqlalchemy.pool import NullPool

from ctpool.config import get_settings
from ctpool.models.base import Base

# Explicit model imports so Alembic autogenerate detects every table.
# Wildcard imports are prohibited; each model is listed individually.
from ctpool.models.certificate import Certificate  # noqa: F401
from ctpool.models.certificate_hostname import CertificateHostname  # noqa: F401
from ctpool.models.db_contention_state import CtDbContentionState  # noqa: F401
from ctpool.models.entry_outcome import CtEntryOutcome  # noqa: F401
from ctpool.models.hostname import Hostname  # noqa: F401
from ctpool.models.ingestion_error import IngestionError  # noqa: F401
from ctpool.models.ingestion_metric import IngestionMetric  # noqa: F401
from ctpool.models.audit_finding import CtAuditFinding  # noqa: F401
from ctpool.models.instance_settings import CtInstanceSettings  # noqa: F401
from ctpool.models.log_backfill_range import CtLogBackfillRange  # noqa: F401
from ctpool.models.log_backfill_state import CtLogBackfillState  # noqa: F401
from ctpool.models.log_runtime_state import CtLogRuntimeState  # noqa: F401
from ctpool.models.log_source import CtLogSource  # noqa: F401
from ctpool.models.log_tail_cursor import CtLogTailCursor  # noqa: F401
from ctpool.models.log_tail_lease import CtLogTailLease  # noqa: F401
from ctpool.models.maintenance_run import CtMaintenanceRun  # noqa: F401
from ctpool.models.observation import CtLogObservation  # noqa: F401
from ctpool.models.prune_run import CtPruneRun  # noqa: F401
from ctpool.models.stats_snapshot import CtStatsSnapshot  # noqa: F401
from ctpool.models.storage_profile_history import CtStorageProfileHistory  # noqa: F401
from ctpool.models.worker_runtime import CtWorkerRuntime  # noqa: F401

config = context.config
target_metadata = Base.metadata

if config.config_file_name is not None:
    fileConfig(config.config_file_name)


def _get_url() -> str:
    """Return the database URL from pydantic-settings (never from alembic.ini)."""
    return str(get_settings().database_url)


def run_migrations_offline() -> None:
    """Run migrations in offline mode (no live DB connection)."""
    url = _get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Any) -> None:
    """Execute migrations against an open connection."""
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Create async engine and run migrations."""
    settings = get_settings()
    configuration = config.get_section(config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = str(settings.database_url)
    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    """Entry point for online (connected) migration mode."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
