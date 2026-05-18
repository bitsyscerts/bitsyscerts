"""Persistence helpers for ``ct_maintenance_runs``.

Each ``ctpool prune-for-storage-profile`` invocation that actually executes
deletes (or that runs through the maintenance loop) is recorded as one
``CtMaintenanceRun`` row.  Dry runs are also recorded so operators can
inspect the most recent plan from the dashboard.

Two-phase write:
    1. ``insert_maintenance_run`` opens the row in ``running`` state.
    2. ``finalize_maintenance_run`` updates it with the final counts and
       a terminal status (``complete`` or ``failed``).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import update
from sqlalchemy.ext.asyncio import async_sessionmaker

from ctpool.models.maintenance_run import CtMaintenanceRun

__all__ = [
    "insert_maintenance_run",
    "finalize_maintenance_run",
]


async def insert_maintenance_run(
    factory: async_sessionmaker[Any],
    *,
    run_type: str,
    mode: str,
    storage_profile: str | None,
    settings_hash: str | None = None,
) -> uuid.UUID:
    """Insert a ``running`` maintenance row and return its id."""
    run_id = uuid.uuid4()
    async with factory() as session:
        async with session.begin():
            session.add(
                CtMaintenanceRun(
                    id=run_id,
                    run_type=run_type,
                    mode=mode,
                    status="running",
                    storage_profile=storage_profile,
                    settings_hash=settings_hash,
                )
            )
    return run_id


async def finalize_maintenance_run(
    factory: async_sessionmaker[Any],
    run_id: uuid.UUID,
    *,
    status: str,
    deleted_certificates: int = 0,
    deleted_certificate_hostnames: int = 0,
    deleted_observations: int = 0,
    deleted_entry_outcomes: int = 0,
    deleted_ingestion_metrics: int = 0,
    preserved_hostnames: int | None = None,
    duration_ms: int | None = None,
    error_message: str | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    """Stamp the maintenance row with terminal counts and status."""
    completed_at = datetime.now(UTC)
    async with factory() as session:
        async with session.begin():
            await session.execute(
                update(CtMaintenanceRun)
                .where(CtMaintenanceRun.id == run_id)
                .values(
                    status=status,
                    completed_at=completed_at,
                    duration_ms=duration_ms,
                    deleted_certificates=deleted_certificates,
                    deleted_certificate_hostnames=deleted_certificate_hostnames,
                    deleted_observations=deleted_observations,
                    deleted_entry_outcomes=deleted_entry_outcomes,
                    deleted_ingestion_metrics=deleted_ingestion_metrics,
                    preserved_hostnames=preserved_hostnames,
                    error_message=error_message,
                    details_json=details,
                )
            )
