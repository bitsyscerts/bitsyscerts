"""Tests for ctpool.worker_registry — worker registration and heartbeat."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ctpool.models.worker_runtime import CtWorkerRuntime
from ctpool.worker_registry import (
    WorkerCounters,
    heartbeat_worker,
    list_active_workers,
    list_stale_workers,
    mark_worker_stopped,
    register_worker,
)

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _commit_register(
    session: AsyncSession, worker_id: str, kind: str
) -> CtWorkerRuntime:
    """Register a worker inside an explicit transaction and return the row."""
    async with session.begin_nested():
        row = await register_worker(session, worker_id=worker_id, worker_kind=kind)
        await session.flush()
    return row


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


async def test_register_worker_creates_row(db_session: AsyncSession) -> None:
    """register_worker inserts a ct_worker_runtime row."""
    row = await _commit_register(db_session, "host1:100", "tail")

    result = await db_session.get(CtWorkerRuntime, row.id)
    assert result is not None
    assert result.worker_id == "host1:100"
    assert result.worker_kind == "tail"


async def test_register_worker_status_is_starting(db_session: AsyncSession) -> None:
    """Freshly registered worker has status='starting'."""
    row = await _commit_register(db_session, "host1:101", "backfill")
    result = await db_session.get(CtWorkerRuntime, row.id)
    assert result is not None
    assert result.status == "starting"


async def test_register_worker_heartbeat_populated(db_session: AsyncSession) -> None:
    """last_heartbeat_at is set on registration."""
    row = await _commit_register(db_session, "host1:102", "tail")
    result = await db_session.get(CtWorkerRuntime, row.id)
    assert result is not None
    assert result.last_heartbeat_at is not None


async def test_register_worker_two_workers_separate_rows(
    db_session: AsyncSession,
) -> None:
    """Two distinct workers produce two separate rows (no deduplication)."""
    row_a = await _commit_register(db_session, "host1:200", "tail")
    row_b = await _commit_register(db_session, "host2:200", "tail")
    assert row_a.id != row_b.id


# ---------------------------------------------------------------------------
# Heartbeat
# ---------------------------------------------------------------------------


async def test_heartbeat_updates_status_and_timestamp(db_session: AsyncSession) -> None:
    """heartbeat_worker changes status and refreshes last_heartbeat_at."""
    row = await _commit_register(db_session, "host1:300", "tail")
    original_hb = row.last_heartbeat_at

    async with db_session.begin_nested():
        await heartbeat_worker(
            db_session, row_id=row.id, status="processing", current_index=42
        )

    await db_session.refresh(row)
    assert row.status == "processing"
    assert row.current_index == 42
    # Heartbeat timestamp must be >= original (may be equal in fast CI).
    assert row.last_heartbeat_at >= original_hb


async def test_heartbeat_updates_counters(db_session: AsyncSession) -> None:
    """heartbeat_worker writes WorkerCounters values to the row."""
    row = await _commit_register(db_session, "host1:301", "backfill")

    counters = WorkerCounters(
        processed_entries=1000,
        stored_certificates=800,
        duplicate_certificates=200,
        observed_hostnames=500,
        new_hostnames=300,
        parse_errors=3,
        retryable_errors=1,
        terminal_errors=2,
        last_error_type="ParseError",
        last_error_message="bad cert",
    )
    async with db_session.begin_nested():
        await heartbeat_worker(
            db_session, row_id=row.id, status="processing", counters=counters
        )

    await db_session.refresh(row)
    assert row.processed_entries == 1000
    assert row.stored_certificates == 800
    assert row.duplicate_certificates == 200
    assert row.observed_hostnames == 500
    assert row.new_hostnames == 300
    assert row.parse_errors == 3
    assert row.retryable_errors == 1
    assert row.terminal_errors == 2
    assert row.last_error_type == "ParseError"
    assert row.last_error_message == "bad cert"


# ---------------------------------------------------------------------------
# Stopped
# ---------------------------------------------------------------------------


async def test_mark_worker_stopped_sets_status(db_session: AsyncSession) -> None:
    """mark_worker_stopped sets status='stopped' and stopped_at."""
    row = await _commit_register(db_session, "host1:400", "tail")

    async with db_session.begin_nested():
        await mark_worker_stopped(db_session, row_id=row.id)

    await db_session.refresh(row)
    assert row.status == "stopped"
    assert row.stopped_at is not None


# ---------------------------------------------------------------------------
# list_active_workers
# ---------------------------------------------------------------------------


async def test_list_active_workers_excludes_stopped(db_session: AsyncSession) -> None:
    """list_active_workers omits rows with status='stopped'."""
    row_a = await _commit_register(db_session, "host1:500", "tail")
    row_b = await _commit_register(db_session, "host1:501", "tail")

    async with db_session.begin_nested():
        await mark_worker_stopped(db_session, row_id=row_b.id)

    active = await list_active_workers(db_session)
    active_ids = {r.id for r in active}
    assert row_a.id in active_ids
    assert row_b.id not in active_ids


async def test_list_active_workers_includes_starting(db_session: AsyncSession) -> None:
    """list_active_workers includes workers in 'starting' status."""
    row = await _commit_register(db_session, "host1:502", "tail")
    active = await list_active_workers(db_session)
    assert any(r.id == row.id for r in active)


# ---------------------------------------------------------------------------
# list_stale_workers
# ---------------------------------------------------------------------------


async def test_list_stale_workers_returns_expired_heartbeat(
    db_session: AsyncSession,
) -> None:
    """Workers with heartbeat older than stale_seconds appear in stale list."""
    row = await _commit_register(db_session, "host1:600", "tail")

    # Force heartbeat to the past via raw SQL to bypass ORM caching.
    past_ts = datetime.now(UTC) - timedelta(seconds=600)
    await db_session.execute(
        text(
            "UPDATE ct_worker_runtime SET last_heartbeat_at = :ts WHERE id = :id"
        ).bindparams(ts=past_ts, id=row.id)
    )

    stale = await list_stale_workers(db_session, stale_seconds=300)
    assert any(r.id == row.id for r in stale)


async def test_list_stale_workers_excludes_fresh_heartbeat(
    db_session: AsyncSession,
) -> None:
    """Workers with a recent heartbeat are NOT stale."""
    row = await _commit_register(db_session, "host1:601", "tail")
    stale = await list_stale_workers(db_session, stale_seconds=300)
    assert all(r.id != row.id for r in stale)


async def test_list_stale_workers_excludes_stopped(db_session: AsyncSession) -> None:
    """Stopped workers are not returned as stale even with old heartbeat."""
    row = await _commit_register(db_session, "host1:602", "tail")

    past_ts = datetime.now(UTC) - timedelta(seconds=600)
    await db_session.execute(
        text(
            "UPDATE ct_worker_runtime SET last_heartbeat_at = :ts WHERE id = :id"
        ).bindparams(ts=past_ts, id=row.id)
    )
    async with db_session.begin_nested():
        await mark_worker_stopped(db_session, row_id=row.id)

    stale = await list_stale_workers(db_session, stale_seconds=300)
    assert all(r.id != row.id for r in stale)
