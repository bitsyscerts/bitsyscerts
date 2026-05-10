"""Tests for ctpool.backfill_state_queries — per-log dashboard summary."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ctpool.backfill_state_queries import query_backfill_state_summary
from ctpool.worker_claim import (
    ensure_log_backfill_state,
    initialize_log_window,
)

pytestmark = pytest.mark.asyncio

_STALE_SECONDS = 300


async def _insert_log_source(session: AsyncSession, *, description: str) -> uuid.UUID:
    log_id = uuid.uuid4()
    await session.execute(
        text(
            """
            INSERT INTO ct_log_sources
                (id, log_id_b64, operator_name, description, url,
                 public_key_b64, log_state, is_eligible_for_tail,
                 is_eligible_for_backfill, source_list)
            VALUES
                (:id, :log_id_b64, 'Op', :description,
                 :url, 'a2V5', 'usable', true, true, 'chrome')
            """
        ).bindparams(
            id=log_id,
            log_id_b64=f"log-{log_id}",
            description=description,
            url=f"https://ct.example.com/{log_id}/",
        )
    )
    return log_id


async def test_summary_empty_returns_zero_counters(db_session: AsyncSession) -> None:
    """An empty ct_log_backfill_state yields all-zero counters."""
    summary = await query_backfill_state_summary(
        db_session, stale_seconds=_STALE_SECONDS
    )
    assert summary["total_logs"] == 0
    assert summary["pending"] == 0
    assert summary["complete"] == 0
    assert summary["items"] == []


async def test_summary_counts_each_status(db_session: AsyncSession) -> None:
    """Counters reflect each row's status; items contain progress."""
    log1 = await _insert_log_source(db_session, description="L1")
    log2 = await _insert_log_source(db_session, description="L2")

    async with db_session.begin_nested():
        await ensure_log_backfill_state(db_session, log_source_id=log1)
        await ensure_log_backfill_state(db_session, log_source_id=log2)
        await initialize_log_window(
            db_session,
            log_source_id=log1,
            backfill_start_index=0,
            backfill_end_index=999,
        )
        await initialize_log_window(
            db_session,
            log_source_id=log2,
            backfill_start_index=0,
            backfill_end_index=99,
        )
        # Force log2 to status="processing" with checkpoint=50
        await db_session.execute(
            text(
                "UPDATE ct_log_backfill_state SET status='processing', "
                "last_checkpoint_index=50 WHERE log_source_id=:id"
            ).bindparams(id=log2)
        )

    summary = await query_backfill_state_summary(
        db_session, stale_seconds=_STALE_SECONDS
    )
    assert summary["total_logs"] == 2
    assert summary["pending"] == 1
    assert summary["processing"] == 1
    items = summary["items"]
    assert len(items) == 2
    by_name = {it["log_name"]: it for it in items}
    assert by_name["L2"]["progress_percent"] == pytest.approx(50.51, abs=0.01)


async def test_summary_marks_stale_claim(db_session: AsyncSession) -> None:
    """A row whose heartbeat predates stale_seconds is marked is_stale."""
    log_id = await _insert_log_source(db_session, description="StaleLog")
    async with db_session.begin_nested():
        await ensure_log_backfill_state(db_session, log_source_id=log_id)

    past = datetime.now(UTC) - timedelta(seconds=600)
    await db_session.execute(
        text(
            "UPDATE ct_log_backfill_state "
            "SET claimed_by='dead-worker', heartbeat_at=:ts, status='claimed' "
            "WHERE log_source_id=:id"
        ).bindparams(ts=past, id=log_id)
    )

    summary = await query_backfill_state_summary(
        db_session, stale_seconds=_STALE_SECONDS
    )
    assert summary["stale"] == 1
    item = summary["items"][0]
    assert item["is_stale"] is True
    assert item["claimed_by"] == "dead-worker"


async def test_progress_percent_helper_handles_edge_cases() -> None:
    """_progress_percent: None inputs and span==0 cases."""
    from ctpool.backfill_state_queries import _progress_percent

    assert _progress_percent(None, 100, 50) is None
    assert _progress_percent(0, None, 50) is None
    assert _progress_percent(0, 100, None) is None
    # span==0 → 100%
    assert _progress_percent(0, 0, 0) == 100.0
    # checkpoint at start
    assert _progress_percent(0, 100, 0) == 0.0
    # at end
    assert _progress_percent(0, 100, 100) == 100.0
