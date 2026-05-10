"""Stale worker-row cleanup for ct_worker_runtime."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ctpool.models.worker_runtime import CtWorkerRuntime

_STATUS_STOPPED = "stopped"


async def reap_stale_worker_rows(
    session: AsyncSession,
    *,
    stale_seconds: int,
) -> list[str]:
    """Mark expired worker-runtime rows as stopped and return their ids.

    Args:
        session: Open async SQLAlchemy session.
        stale_seconds: Heartbeat age beyond which a worker is considered gone.

    Returns:
        Worker identity strings for rows that were marked stopped.
    """
    cutoff = datetime.now(UTC) - timedelta(seconds=stale_seconds)
    result = await session.execute(
        select(CtWorkerRuntime.id, CtWorkerRuntime.worker_id)
        .where(CtWorkerRuntime.status != _STATUS_STOPPED)
        .where(CtWorkerRuntime.last_heartbeat_at < cutoff)
    )
    stale_rows = result.all()
    if not stale_rows:
        return []

    stale_ids: list[uuid.UUID] = [row.id for row in stale_rows]
    now = datetime.now(UTC)
    await session.execute(
        update(CtWorkerRuntime)
        .where(CtWorkerRuntime.id.in_(stale_ids))
        .values(status=_STATUS_STOPPED, stopped_at=now, updated_at=now)
    )
    return [row.worker_id for row in stale_rows]
