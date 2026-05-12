"""Tests for ctpool.worker_queries — worker activity query for stats pipeline."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ctpool.models.worker_runtime import CtWorkerRuntime
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
    log_name: str | None = None,
    direction: str | None = None,
    current_index: int | None = None,
    last_successful_index: int | None = None,
    batch_start_index: int | None = None,
    batch_end_index: int | None = None,
    details_json: dict[str, object] | None = None,
) -> uuid.UUID:
    """Insert a ct_worker_runtime row with controlled heartbeat time."""
    row_id = uuid.uuid4()
    now = datetime.now(UTC)
    hb = now - timedelta(seconds=heartbeat_offset_seconds)
    session.add(
        CtWorkerRuntime(
            id=row_id,
            worker_id=worker_id,
            worker_kind=worker_kind,
            log_source_id=log_source_id,
            log_name=log_name,
            direction=direction,
            status=status,
            last_heartbeat_at=hb,
            started_at=now,
            updated_at=now,
            current_index=current_index,
            last_successful_index=last_successful_index,
            batch_start_index=batch_start_index,
            batch_end_index=batch_end_index,
            details_json=details_json,
        )
    )
    await session.flush()
    return row_id


async def _insert_backfill_state(
    session: AsyncSession,
    *,
    log_source_id: uuid.UUID,
    claimed_by: str | None,
    status: str,
    checkpoint_index: int | None = None,
    backfill_start_index: int | None = None,
    backfill_end_index: int | None = None,
    retry_count: int = 0,
    next_retry_at: datetime | None = None,
    rate_limited_until: datetime | None = None,
    last_error_type: str | None = None,
    last_error_message: str | None = None,
) -> None:
    await session.execute(
        text(
            """
            INSERT INTO ct_log_backfill_state
                (log_source_id, claimed_by, status, last_checkpoint_index,
                 backfill_start_index, backfill_end_index, retry_count,
                 next_retry_at, rate_limited_until, last_error_type,
                 last_error_message)
            VALUES
                (:log_source_id, :claimed_by, :status, :checkpoint_index,
                 :backfill_start_index, :backfill_end_index, :retry_count,
                 :next_retry_at, :rate_limited_until, :last_error_type,
                 :last_error_message)
            """
        ).bindparams(
            log_source_id=log_source_id,
            claimed_by=claimed_by,
            status=status,
            checkpoint_index=checkpoint_index,
            backfill_start_index=backfill_start_index,
            backfill_end_index=backfill_end_index,
            retry_count=retry_count,
            next_retry_at=next_retry_at,
            rate_limited_until=rate_limited_until,
            last_error_type=last_error_type,
            last_error_message=last_error_message,
        )
    )


async def _insert_tail_cursor(
    session: AsyncSession,
    *,
    log_source_id: uuid.UUID,
    next_index: int,
) -> None:
    await session.execute(
        text(
            """
            INSERT INTO ct_log_tail_cursors (log_source_id, next_index)
            VALUES (:log_source_id, :next_index)
            """
        ).bindparams(log_source_id=log_source_id, next_index=next_index)
    )


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
    assert summary["stats_active"] == 0
    assert summary["maintenance_active"] == 0
    assert summary["unknown_active"] == 0
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
    assert summary["stats_active"] == 0
    assert summary["maintenance_active"] == 0
    assert len(summary["items"]) == 2


async def test_query_worker_summary_counts_singleton_and_unknown_workers(
    db_session: AsyncSession,
) -> None:
    """Singleton service workers are counted separately from unknown kinds."""
    await _insert_worker(
        db_session,
        worker_id="s1",
        worker_kind="stats-snapshotter",
        status="processing",
    )
    await _insert_worker(
        db_session,
        worker_id="m1",
        worker_kind="maintenance",
        status="idle",
    )
    await _insert_worker(
        db_session,
        worker_id="u1",
        worker_kind="unknown",
        status="idle",
    )

    summary = await query_worker_summary(db_session, stale_seconds=_STALE_SECONDS)
    assert summary["active_total"] == 3
    assert summary["stats_active"] == 1
    assert summary["maintenance_active"] == 1
    assert summary["unknown_active"] == 1


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


async def test_query_worker_summary_enriches_backfill_claim(
    db_session: AsyncSession,
) -> None:
    """Backfill workers inherit assigned-log and checkpoint data from claim state."""
    log_source_id = await _insert_log_source(db_session)
    next_retry_at = datetime.now(UTC) + timedelta(minutes=5)
    rate_limited_until = datetime.now(UTC) + timedelta(minutes=10)
    await _insert_worker(
        db_session,
        worker_id="bf1",
        worker_kind="backfill",
        status="retrying",
    )
    await _insert_backfill_state(
        db_session,
        log_source_id=log_source_id,
        claimed_by="bf1",
        status="retrying",
        checkpoint_index=30284250,
        backfill_start_index=30284200,
        backfill_end_index=30284400,
        retry_count=2,
        next_retry_at=next_retry_at,
        rate_limited_until=rate_limited_until,
        last_error_type="RateLimitError",
        last_error_message="too many requests",
    )

    summary = await query_worker_summary(db_session, stale_seconds=_STALE_SECONDS)
    item = summary["items"][0]
    assert item["log_source_id"] == str(log_source_id)
    assert item["log_name"] == "Test Log"
    assert item["log_url"] == "https://ct.example.com/"
    assert item["log_operator"] == "Op"
    assert item["checkpoint_index"] == 30284250
    assert item["batch_start_index"] == 30284200
    assert item["batch_end_index"] == 30284400
    assert item["retry_count"] == 2
    assert item["next_retry_at"] == next_retry_at.isoformat()
    assert item["rate_limited_until"] == rate_limited_until.isoformat()
    assert item["last_error_type"] == "RateLimitError"
    assert item["last_error_message"] == "Upstream rate limit"


async def test_query_worker_summary_prefers_runtime_details_and_tail_cursor(
    db_session: AsyncSession,
) -> None:
    """Runtime rows surface direct tail assignment, progress, and per-minute rates."""
    log_source_id = await _insert_log_source(db_session)
    await _insert_tail_cursor(db_session, log_source_id=log_source_id, next_index=777)
    await _insert_worker(
        db_session,
        worker_id="tail-1",
        worker_kind="tail",
        status="processing",
        log_source_id=log_source_id,
        direction="tail",
        current_index=None,
        last_successful_index=776,
        batch_start_index=760,
        batch_end_index=780,
        details_json={
            "observations_per_min": 1200.0,
            "new_unique_certificates_per_min": 120.0,
            "duplicate_certificates_per_min": 1080.0,
            "new_unique_hostnames_per_min": 55.0,
            "known_hostnames_per_min": 945.0,
            "checkpoint_index": 776,
        },
    )

    summary = await query_worker_summary(db_session, stale_seconds=_STALE_SECONDS)
    item = summary["items"][0]
    assert item["log_name"] == "Test Log"
    assert item["log_operator"] == "Op"
    assert item["current_index"] == 777
    assert item["checkpoint_index"] == 776
    assert item["batch_start_index"] == 760
    assert item["batch_end_index"] == 780
    assert item["observations_per_min"] == 1200.0
    assert item["new_unique_certificates_per_min"] == 120.0
    assert item["duplicate_certificates_per_min"] == 1080.0
    assert item["new_unique_hostnames_per_min"] == 55.0
    assert item["known_hostnames_per_min"] == 945.0


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
