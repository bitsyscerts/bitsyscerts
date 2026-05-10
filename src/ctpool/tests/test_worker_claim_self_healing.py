"""Tests for Sprint 3 self-healing semantics on ct_log_backfill_state.

Covers retry-budget bookkeeping, rate-limit cooldown persistence, and
``mark_log_paused`` budget exhaustion behavior.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ctpool.worker_claim import (
    claim_log_for_worker,
    ensure_log_backfill_state,
    increment_terminal_error_count,
    mark_log_paused,
    mark_log_retrying,
    update_log_progress,
)

pytestmark = pytest.mark.asyncio

_STALE_SECONDS = 300


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
                (:id, :log_id_b64, 'Op', 'Test Log', 'https://ct.example.com/',
                 'a2V5', 'usable', true, true, 'chrome')
            """
        ).bindparams(id=log_id, log_id_b64=f"log-{log_id}")
    )
    return log_id


async def _setup_claimed(session: AsyncSession, worker: str) -> uuid.UUID:
    log_id = await _insert_log_source(session)
    async with session.begin_nested():
        await ensure_log_backfill_state(session, log_source_id=log_id)
    async with session.begin_nested():
        await claim_log_for_worker(
            session,
            log_source_id=log_id,
            worker_id=worker,
            stale_seconds=_STALE_SECONDS,
        )
    return log_id


async def test_mark_log_retrying_increments_retry_counters(
    db_session: AsyncSession,
) -> None:
    """Each retry transition bumps retry_count and retryable_error_count."""
    log_id = await _setup_claimed(db_session, "w1")

    async with db_session.begin_nested():
        await mark_log_retrying(
            db_session,
            log_source_id=log_id,
            worker_id="w1",
            error_type="FetchError",
            error_message="boom",
        )

    row = (
        await db_session.execute(
            text(
                "SELECT retry_count, retryable_error_count, status, "
                "last_error_at FROM ct_log_backfill_state "
                "WHERE log_source_id=:id"
            ).bindparams(id=log_id)
        )
    ).first()
    assert row is not None
    assert row[0] == 1
    assert row[1] == 1
    assert row[2] == "retrying"
    assert row[3] is not None


async def test_mark_log_retrying_with_retry_after_sets_rate_limited(
    db_session: AsyncSession,
) -> None:
    """A 429 with Retry-After flips status to rate_limited and stores cooldown."""
    log_id = await _setup_claimed(db_session, "w1")

    async with db_session.begin_nested():
        await mark_log_retrying(
            db_session,
            log_source_id=log_id,
            worker_id="w1",
            error_type="RateLimitError",
            error_message="429",
            retry_after_seconds=60,
        )

    row = (
        await db_session.execute(
            text(
                "SELECT status, rate_limited_until, next_retry_at "
                "FROM ct_log_backfill_state WHERE log_source_id=:id"
            ).bindparams(id=log_id)
        )
    ).first()
    assert row is not None
    assert row[0] == "rate_limited"
    assert row[1] is not None
    assert row[2] is not None


async def test_mark_log_paused_releases_claim(db_session: AsyncSession) -> None:
    """Pausing the log clears the worker claim so it isn't auto-re-picked."""
    log_id = await _setup_claimed(db_session, "w1")

    async with db_session.begin_nested():
        await mark_log_paused(
            db_session,
            log_source_id=log_id,
            worker_id="w1",
            error_type="UnknownError",
            error_message="exhausted",
        )

    row = (
        await db_session.execute(
            text(
                "SELECT status, claimed_by FROM ct_log_backfill_state "
                "WHERE log_source_id=:id"
            ).bindparams(id=log_id)
        )
    ).first()
    assert row is not None
    assert row[0] == "paused"
    assert row[1] is None


async def test_increment_terminal_error_count_persists(
    db_session: AsyncSession,
) -> None:
    """Recording a bad CT entry increments the per-log terminal counter."""
    log_id = await _setup_claimed(db_session, "w1")

    async with db_session.begin_nested():
        await increment_terminal_error_count(db_session, log_source_id=log_id)
        await increment_terminal_error_count(db_session, log_source_id=log_id)

    row = (
        await db_session.execute(
            text(
                "SELECT terminal_error_count FROM ct_log_backfill_state "
                "WHERE log_source_id=:id"
            ).bindparams(id=log_id)
        )
    ).first()
    assert row is not None
    assert row[0] == 2


async def test_successful_progress_resets_retry_count(
    db_session: AsyncSession,
) -> None:
    """A successful batch (status=processing, no error) clears retry_count."""
    log_id = await _setup_claimed(db_session, "w1")
    async with db_session.begin_nested():
        await mark_log_retrying(
            db_session,
            log_source_id=log_id,
            worker_id="w1",
            error_type="FetchError",
            error_message="x",
        )
    async with db_session.begin_nested():
        await update_log_progress(
            db_session,
            log_source_id=log_id,
            worker_id="w1",
            checkpoint_index=42,
            status="processing",
        )

    row = (
        await db_session.execute(
            text(
                "SELECT retry_count, retryable_error_count, "
                "rate_limited_until, next_retry_at "
                "FROM ct_log_backfill_state WHERE log_source_id=:id"
            ).bindparams(id=log_id)
        )
    ).first()
    assert row is not None
    # retry_count is reset on successful batch …
    assert row[0] == 0
    # … but the cumulative retryable_error_count is preserved.
    assert row[1] == 1
    assert row[2] is None
    assert row[3] is None
