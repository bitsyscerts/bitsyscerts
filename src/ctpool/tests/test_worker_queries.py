"""Tests for ctpool.worker_queries — worker activity query for stats pipeline."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ctpool.worker_queries import query_worker_summary

pytestmark = pytest.mark.asyncio

_STALE_SECONDS = 300


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _insert_log_source(session: AsyncSession) -> uuid.UUID:
    log_id = uuid.uuid4()
    await session.execute(
        text(
            """
            INSERT INTO ct_log_sources
                (id, log_id_b64, operator_name, description, url,
                 public_key_b64, log_state, is_eligible_for_tail,
                 is_eligible_for_backfill, source_list)
            VALUES
                (:id, :b64, 'Op', 'Test Log', 'https://ct.example.com/',
                 'a2V5', 'usable', true, true, 'chrome')
            """
        ).bindparams(id=log_id, b64=f"b64-{log_id}")
    )
    return log_id


async def _insert_worker(
    session: AsyncSession,
    *,
    worker_id: str,
    worker_kind: str,
    status: str,
    log_source_id: uuid.UUID | None = None,
    heartbeat_offset_seconds: int = 0,
) -> uuid.UUID:
    """Insert a ct_worker_runtime row with controlled heartbeat time."""
    row_id = uuid.uuid4()
    now = datetime.now(UTC)
    hb = now - timedelta(seconds=heartbeat_offset_seconds)
    await session.execute(
        text(
            """
            INSERT INTO ct_worker_runtime
                (id, worker_id, worker_kind, log_source_id, status,
                 last_heartbeat_at, started_at, updated_at,
                 processed_entries, stored_certificates, duplicate_certificates,
                 observed_hostnames, new_hostnames, parse_errors,
                 retryable_errors, terminal_errors)
            VALUES
                (:id, :worker_id, :worker_kind, :log_source_id, :status,
                 :hb, :now, :now, 0, 0, 0, 0, 0, 0, 0, 0)
            """
        ).bindparams(
            id=row_id,
            worker_id=worker_id,
            worker_kind=worker_kind,
            log_source_id=log_source_id,
            status=status,
            hb=hb,
            now=now,
        )
    )
    return row_id


# ---------------------------------------------------------------------------
# query_worker_summary
# ---------------------------------------------------------------------------


async def test_query_worker_summary_empty(db_session: AsyncSession) -> None:
    """No workers → all counts zero, items empty."""
    summary = await query_worker_summary(db_session, stale_seconds=_STALE_SECONDS)
    assert summary["active_total"] == 0
    assert summary["stale_total"] == 0
    assert summary["tail_active"] == 0
    assert summary["backfill_active"] == 0
    assert summary["items"] == []


async def test_query_worker_summary_counts_active(db_session: AsyncSession) -> None:
    """Active tail and backfill workers are counted correctly."""
    await _insert_worker(
        db_session, worker_id="t1", worker_kind="tail", status="processing"
    )
    await _insert_worker(
        db_session, worker_id="b1", worker_kind="backfill", status="claimed"
    )

    summary = await query_worker_summary(db_session, stale_seconds=_STALE_SECONDS)
    assert summary["active_total"] == 2
    assert summary["tail_active"] == 1
    assert summary["backfill_active"] == 1
    assert len(summary["items"]) == 2


async def test_query_worker_summary_excludes_stopped(db_session: AsyncSession) -> None:
    """Stopped workers are not returned in the summary."""
    await _insert_worker(
        db_session, worker_id="t1", worker_kind="tail", status="processing"
    )
    await _insert_worker(
        db_session, worker_id="t2", worker_kind="tail", status="stopped"
    )

    summary = await query_worker_summary(db_session, stale_seconds=_STALE_SECONDS)
    assert summary["active_total"] == 1
    assert len(summary["items"]) == 1
    assert summary["items"][0]["worker_id"] == "t1"


async def test_query_worker_summary_stale_detection(db_session: AsyncSession) -> None:
    """Worker with heartbeat older than stale_seconds is flagged stale."""
    await _insert_worker(
        db_session,
        worker_id="stale-worker",
        worker_kind="tail",
        status="processing",
        heartbeat_offset_seconds=600,  # 600s > 300s threshold
    )

    summary = await query_worker_summary(db_session, stale_seconds=_STALE_SECONDS)
    assert summary["stale_total"] == 1
    assert summary["active_total"] == 0
    stale_item = summary["items"][0]
    assert stale_item["is_stale"] is True


async def test_query_worker_summary_fresh_not_stale(db_session: AsyncSession) -> None:
    """Worker with recent heartbeat is NOT stale."""
    await _insert_worker(
        db_session,
        worker_id="fresh-worker",
        worker_kind="backfill",
        status="processing",
        heartbeat_offset_seconds=10,  # 10s < 300s threshold
    )

    summary = await query_worker_summary(db_session, stale_seconds=_STALE_SECONDS)
    assert summary["stale_total"] == 0
    assert summary["active_total"] == 1
    assert summary["items"][0]["is_stale"] is False


async def test_query_worker_summary_log_source_id_none_allowed(
    db_session: AsyncSession,
) -> None:
    """Worker without an assigned log returns log_source_id=None in items."""
    await _insert_worker(
        db_session,
        worker_id="idle-worker",
        worker_kind="tail",
        status="idle",
        log_source_id=None,
    )

    summary = await query_worker_summary(db_session, stale_seconds=_STALE_SECONDS)
    assert len(summary["items"]) == 1
    assert summary["items"][0]["log_source_id"] is None


async def test_query_worker_summary_includes_heartbeat_age(
    db_session: AsyncSession,
) -> None:
    """items contain last_heartbeat_age_seconds."""
    await _insert_worker(
        db_session,
        worker_id="w1",
        worker_kind="tail",
        status="processing",
        heartbeat_offset_seconds=30,
    )

    summary = await query_worker_summary(db_session, stale_seconds=_STALE_SECONDS)
    age = summary["items"][0]["last_heartbeat_age_seconds"]
    assert age >= 25  # allow a few seconds of test execution time
