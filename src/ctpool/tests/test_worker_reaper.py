"""Tests for automatic stale worker cleanup."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ctpool.models.worker_runtime import CtWorkerRuntime
from ctpool.worker_reaper import reap_stale_worker_rows
from ctpool.worker_registry import register_worker

pytestmark = pytest.mark.asyncio


async def _register_worker(
    session: AsyncSession,
    worker_id: str,
    worker_kind: str,
) -> CtWorkerRuntime:
    async with session.begin_nested():
        row = await register_worker(
            session,
            worker_id=worker_id,
            worker_kind=worker_kind,
        )
        await session.flush()
    return row


async def test_reap_stale_worker_rows_marks_expired_workers_stopped(
    db_session: AsyncSession,
) -> None:
    """Expired worker rows are marked stopped and omitted from active state."""
    stale_row = await _register_worker(db_session, "host:100", "tail")
    fresh_row = await _register_worker(db_session, "host:101", "backfill")

    past_ts = datetime.now(UTC) - timedelta(seconds=600)
    await db_session.execute(
        text(
            "UPDATE ct_worker_runtime SET last_heartbeat_at = :ts WHERE id = :id"
        ).bindparams(ts=past_ts, id=stale_row.id)
    )

    reaped = await reap_stale_worker_rows(db_session, stale_seconds=300)

    await db_session.refresh(stale_row)
    await db_session.refresh(fresh_row)
    assert reaped == ["host:100"]
    assert stale_row.status == "stopped"
    assert stale_row.stopped_at is not None
    assert fresh_row.status == "starting"
    assert fresh_row.stopped_at is None


async def test_reap_stale_worker_rows_ignores_fresh_workers(
    db_session: AsyncSession,
) -> None:
    """Fresh worker rows are left untouched."""
    fresh_row = await _register_worker(db_session, "host:200", "tail")

    reaped = await reap_stale_worker_rows(db_session, stale_seconds=300)

    await db_session.refresh(fresh_row)
    assert reaped == []
    assert fresh_row.status == "starting"
    assert fresh_row.stopped_at is None
