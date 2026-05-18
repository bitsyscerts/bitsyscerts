"""Stats query for the most recent ``ct_maintenance_runs`` row.

Kept in its own module so the stats assembler does not pull in the full
maintenance recorder/orchestrator import graph.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ctpool.models.maintenance_run import CtMaintenanceRun


async def query_latest_maintenance_run(
    session: AsyncSession,
) -> dict[str, Any] | None:
    """Return a dict snapshot of the most recent maintenance run.

    Returns ``None`` when no row exists yet.
    """
    stmt = (
        select(CtMaintenanceRun).order_by(CtMaintenanceRun.started_at.desc()).limit(1)
    )
    row = (await session.execute(stmt)).scalar_one_or_none()
    if row is None:
        return None
    return _row_to_dict(row)


def _row_to_dict(row: CtMaintenanceRun) -> dict[str, Any]:
    """Convert a maintenance run ORM row into a JSON-friendly dict."""
    return {
        "id": str(row.id),
        "run_type": row.run_type,
        "mode": row.mode,
        "status": row.status,
        "started_at": row.started_at,
        "completed_at": row.completed_at,
        "duration_ms": row.duration_ms,
        "storage_profile": row.storage_profile,
        "deleted": {
            "certificates": int(row.deleted_certificates or 0),
            "certificate_hostnames": int(row.deleted_certificate_hostnames or 0),
            "observations": int(row.deleted_observations or 0),
            "entry_outcomes": int(row.deleted_entry_outcomes or 0),
            "ingestion_metrics": int(row.deleted_ingestion_metrics or 0),
        },
        "preserved_hostnames": row.preserved_hostnames,
        "error_message": row.error_message,
    }


def compute_next_due(
    last_started_at: datetime | None, interval_seconds: int
) -> datetime | None:
    """Project the next-due timestamp from the last started_at + interval."""
    if last_started_at is None or interval_seconds <= 0:
        return None
    return last_started_at + timedelta(seconds=interval_seconds)


def is_lite_enforced(
    last_run: dict[str, Any] | None,
    *,
    interval_seconds: int,
    grace_factor: float = 2.0,
) -> bool:
    """Return True iff maintenance is actively enforcing retention.

    A currently-executing run (``status='running'``) is treated as enforced
    when it started within the grace window — the loop is healthy and a
    completed result is imminent.  A completed execute run is enforced when
    its ``completed_at`` is within the grace window.  Any other status
    (failed, dry_run, stuck) returns False.

    ``grace_factor`` lets one missed cycle slip before the dashboard flips
    the indicator.
    """
    if last_run is None:
        return False
    status = last_run.get("status")
    if status == "running":
        started_at = last_run.get("started_at")
        if started_at is None:
            return False
        age = (datetime.now(UTC) - started_at).total_seconds()
        return bool(age <= interval_seconds * grace_factor)
    if status != "complete":
        return False
    if last_run.get("mode") != "execute":
        return False
    completed_at = last_run.get("completed_at")
    if completed_at is None:
        return False
    age = (datetime.now(UTC) - completed_at).total_seconds()
    return bool(age <= interval_seconds * grace_factor)
