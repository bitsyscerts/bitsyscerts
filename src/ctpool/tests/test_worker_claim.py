"""Tests for ctpool.worker_claim — per-log backfill ownership semantics."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ctpool.models.log_backfill_state import CtLogBackfillState
from ctpool.worker_claim import (
    claim_log_for_worker,
    ensure_log_backfill_state,
    mark_log_complete,
    reap_stale_log_claims,
    release_log_claim,
    update_log_checkpoint,
)

pytestmark = pytest.mark.asyncio

_STALE_SECONDS = 300


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _insert_log_source(session: AsyncSession) -> uuid.UUID:
    """Insert a minimal ct_log_sources row and return its id."""
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


async def _ensure(session: AsyncSession, log_id: uuid.UUID) -> CtLogBackfillState:
    async with session.begin_nested():
        row = await ensure_log_backfill_state(session, log_source_id=log_id)
        await session.flush()
    return row


# ---------------------------------------------------------------------------
# ensure_log_backfill_state
# ---------------------------------------------------------------------------


async def test_ensure_creates_row_on_first_call(db_session: AsyncSession) -> None:
    """ensure_log_backfill_state creates a row when none exists."""
    log_id = await _insert_log_source(db_session)
    row = await _ensure(db_session, log_id)
    assert row is not None
    assert row.log_source_id == log_id
    assert row.status == "pending"


async def test_ensure_is_idempotent(db_session: AsyncSession) -> None:
    """ensure_log_backfill_state called twice does not raise and returns same row."""
    log_id = await _insert_log_source(db_session)
    row1 = await _ensure(db_session, log_id)
    row2 = await _ensure(db_session, log_id)
    assert row1.log_source_id == row2.log_source_id


# ---------------------------------------------------------------------------
# claim_log_for_worker
# ---------------------------------------------------------------------------


async def test_claim_log_unclaimed(db_session: AsyncSession) -> None:
    """A worker can claim an unclaimed log."""
    log_id = await _insert_log_source(db_session)
    await _ensure(db_session, log_id)

    async with db_session.begin_nested():
        claimed = await claim_log_for_worker(
            db_session,
            log_source_id=log_id,
            worker_id="worker-a",
            stale_seconds=_STALE_SECONDS,
        )

    assert claimed is True
    result = await db_session.execute(
        text(
            "SELECT claimed_by FROM ct_log_backfill_state WHERE log_source_id = :id"
        ).bindparams(id=log_id)
    )
    row = result.first()
    assert row is not None
    assert row[0] == "worker-a"


async def test_claim_log_second_worker_fails(db_session: AsyncSession) -> None:
    """A freshly claimed log cannot be claimed by a second worker."""
    log_id = await _insert_log_source(db_session)
    await _ensure(db_session, log_id)

    async with db_session.begin_nested():
        await claim_log_for_worker(
            db_session,
            log_source_id=log_id,
            worker_id="worker-a",
            stale_seconds=_STALE_SECONDS,
        )

    async with db_session.begin_nested():
        second_claim = await claim_log_for_worker(
            db_session,
            log_source_id=log_id,
            worker_id="worker-b",
            stale_seconds=_STALE_SECONDS,
        )

    assert second_claim is False


async def test_claim_log_stale_claim_takeover(db_session: AsyncSession) -> None:
    """A worker may take over a log whose claim heartbeat has expired."""
    log_id = await _insert_log_source(db_session)
    await _ensure(db_session, log_id)

    # Simulate stale heartbeat directly in DB.
    past = datetime.now(UTC) - timedelta(seconds=600)
    await db_session.execute(
        text(
            "UPDATE ct_log_backfill_state "
            "SET claimed_by='old-worker', heartbeat_at=:ts "
            "WHERE log_source_id=:id"
        ).bindparams(ts=past, id=log_id)
    )

    async with db_session.begin_nested():
        claimed = await claim_log_for_worker(
            db_session,
            log_source_id=log_id,
            worker_id="new-worker",
            stale_seconds=_STALE_SECONDS,
        )

    assert claimed is True
    result = await db_session.execute(
        text(
            "SELECT claimed_by FROM ct_log_backfill_state WHERE log_source_id = :id"
        ).bindparams(id=log_id)
    )
    assert result.scalar_one() == "new-worker"


# ---------------------------------------------------------------------------
# release_log_claim
# ---------------------------------------------------------------------------


async def test_release_log_claim_resets_to_pending(db_session: AsyncSession) -> None:
    """release_log_claim resets claimed_by and status to pending."""
    log_id = await _insert_log_source(db_session)
    await _ensure(db_session, log_id)

    async with db_session.begin_nested():
        await claim_log_for_worker(
            db_session,
            log_source_id=log_id,
            worker_id="worker-a",
            stale_seconds=_STALE_SECONDS,
        )

    async with db_session.begin_nested():
        await release_log_claim(db_session, log_source_id=log_id)

    result = await db_session.execute(
        text(
            "SELECT claimed_by, status FROM ct_log_backfill_state "
            "WHERE log_source_id = :id"
        ).bindparams(id=log_id)
    )
    row = result.first()
    assert row is not None
    assert row[0] is None  # claimed_by
    assert row[1] == "pending"


# ---------------------------------------------------------------------------
# update_log_checkpoint
# ---------------------------------------------------------------------------


async def test_update_log_checkpoint_persists_index(db_session: AsyncSession) -> None:
    """update_log_checkpoint writes last_checkpoint_index."""
    log_id = await _insert_log_source(db_session)
    await _ensure(db_session, log_id)

    async with db_session.begin_nested():
        await claim_log_for_worker(
            db_session,
            log_source_id=log_id,
            worker_id="worker-a",
            stale_seconds=_STALE_SECONDS,
        )

    async with db_session.begin_nested():
        await update_log_checkpoint(
            db_session,
            log_source_id=log_id,
            worker_id="worker-a",
            checkpoint_index=99_000,
        )

    result = await db_session.execute(
        text(
            "SELECT last_checkpoint_index FROM ct_log_backfill_state "
            "WHERE log_source_id = :id"
        ).bindparams(id=log_id)
    )
    assert result.scalar_one() == 99_000


# ---------------------------------------------------------------------------
# mark_log_complete
# ---------------------------------------------------------------------------


async def test_mark_log_complete_sets_status(db_session: AsyncSession) -> None:
    """mark_log_complete sets status='complete' and clears claim."""
    log_id = await _insert_log_source(db_session)
    await _ensure(db_session, log_id)

    async with db_session.begin_nested():
        await claim_log_for_worker(
            db_session,
            log_source_id=log_id,
            worker_id="worker-a",
            stale_seconds=_STALE_SECONDS,
        )

    async with db_session.begin_nested():
        await mark_log_complete(db_session, log_source_id=log_id)

    result = await db_session.execute(
        text(
            "SELECT status, claimed_by FROM ct_log_backfill_state "
            "WHERE log_source_id = :id"
        ).bindparams(id=log_id)
    )
    row = result.first()
    assert row is not None
    assert row[0] == "complete"
    assert row[1] is None  # claimed_by cleared


# ---------------------------------------------------------------------------
# reap_stale_log_claims
# ---------------------------------------------------------------------------


async def test_reap_stale_log_claims_resets_stale(db_session: AsyncSession) -> None:
    """reap_stale_log_claims resets claims with expired heartbeat."""
    log_id = await _insert_log_source(db_session)
    await _ensure(db_session, log_id)

    past = datetime.now(UTC) - timedelta(seconds=600)
    await db_session.execute(
        text(
            "UPDATE ct_log_backfill_state "
            "SET claimed_by='old-worker', heartbeat_at=:ts, status='claimed' "
            "WHERE log_source_id=:id"
        ).bindparams(ts=past, id=log_id)
    )

    async with db_session.begin_nested():
        reaped = await reap_stale_log_claims(db_session, stale_seconds=_STALE_SECONDS)

    assert log_id in reaped

    result = await db_session.execute(
        text(
            "SELECT claimed_by FROM ct_log_backfill_state WHERE log_source_id = :id"
        ).bindparams(id=log_id)
    )
    assert result.scalar_one() is None


async def test_reap_stale_log_claims_leaves_fresh(db_session: AsyncSession) -> None:
    """reap_stale_log_claims does not touch claims with fresh heartbeat."""
    log_id = await _insert_log_source(db_session)
    await _ensure(db_session, log_id)

    async with db_session.begin_nested():
        await claim_log_for_worker(
            db_session,
            log_source_id=log_id,
            worker_id="fresh-worker",
            stale_seconds=_STALE_SECONDS,
        )

    async with db_session.begin_nested():
        reaped = await reap_stale_log_claims(db_session, stale_seconds=_STALE_SECONDS)

    assert log_id not in reaped


# ---------------------------------------------------------------------------
# initialize_log_window
# ---------------------------------------------------------------------------


async def test_initialize_log_window_sets_bounds_and_checkpoint(
    db_session: AsyncSession,
) -> None:
    """initialize_log_window writes start/end and seeds checkpoint=start."""
    from ctpool.worker_claim import initialize_log_window

    log_id = await _insert_log_source(db_session)
    await _ensure(db_session, log_id)

    async with db_session.begin_nested():
        await initialize_log_window(
            db_session,
            log_source_id=log_id,
            backfill_start_index=1_000,
            backfill_end_index=10_000,
        )

    result = await db_session.execute(
        text(
            "SELECT backfill_start_index, backfill_end_index, "
            "last_checkpoint_index FROM ct_log_backfill_state "
            "WHERE log_source_id=:id"
        ).bindparams(id=log_id)
    )
    row = result.first()
    assert row is not None
    assert row[0] == 1_000
    assert row[1] == 10_000
    assert row[2] == 1_000


async def test_initialize_log_window_preserves_existing_checkpoint(
    db_session: AsyncSession,
) -> None:
    """If a checkpoint already exists, initialize_log_window does not reset it."""
    from ctpool.worker_claim import initialize_log_window

    log_id = await _insert_log_source(db_session)
    await _ensure(db_session, log_id)

    await db_session.execute(
        text(
            "UPDATE ct_log_backfill_state "
            "SET last_checkpoint_index=5_000 WHERE log_source_id=:id"
        ).bindparams(id=log_id)
    )

    async with db_session.begin_nested():
        await initialize_log_window(
            db_session,
            log_source_id=log_id,
            backfill_start_index=1_000,
            backfill_end_index=10_000,
        )

    result = await db_session.execute(
        text(
            "SELECT last_checkpoint_index FROM ct_log_backfill_state "
            "WHERE log_source_id=:id"
        ).bindparams(id=log_id)
    )
    assert result.scalar_one() == 5_000


# ---------------------------------------------------------------------------
# claim_any_eligible_log
# ---------------------------------------------------------------------------


async def test_claim_any_eligible_log_picks_one(db_session: AsyncSession) -> None:
    """claim_any_eligible_log returns and claims an unclaimed log."""
    from ctpool.worker_claim import claim_any_eligible_log

    log_id = await _insert_log_source(db_session)
    await _ensure(db_session, log_id)

    async with db_session.begin_nested():
        row = await claim_any_eligible_log(
            db_session,
            worker_id="worker-a",
            stale_seconds=_STALE_SECONDS,
        )

    assert row is not None
    assert row.log_source_id == log_id
    assert row.claimed_by == "worker-a"


async def test_claim_any_eligible_log_skips_complete(
    db_session: AsyncSession,
) -> None:
    """Logs already marked complete are not returned."""
    from ctpool.worker_claim import claim_any_eligible_log

    log_id = await _insert_log_source(db_session)
    await _ensure(db_session, log_id)
    async with db_session.begin_nested():
        await mark_log_complete(db_session, log_source_id=log_id)

    async with db_session.begin_nested():
        row = await claim_any_eligible_log(
            db_session,
            worker_id="worker-a",
            stale_seconds=_STALE_SECONDS,
        )

    assert row is None


async def test_claim_any_eligible_log_skips_freshly_claimed(
    db_session: AsyncSession,
) -> None:
    """Two fresh workers do not claim the same log."""
    from ctpool.worker_claim import claim_any_eligible_log

    log_id = await _insert_log_source(db_session)
    await _ensure(db_session, log_id)

    async with db_session.begin_nested():
        first = await claim_any_eligible_log(
            db_session, worker_id="w1", stale_seconds=_STALE_SECONDS
        )
    assert first is not None

    async with db_session.begin_nested():
        second = await claim_any_eligible_log(
            db_session, worker_id="w2", stale_seconds=_STALE_SECONDS
        )
    assert second is None


async def test_claim_any_eligible_log_takes_over_stale(
    db_session: AsyncSession,
) -> None:
    """A stale claim can be taken over by a fresh worker."""
    from ctpool.worker_claim import claim_any_eligible_log

    log_id = await _insert_log_source(db_session)
    await _ensure(db_session, log_id)

    past = datetime.now(UTC) - timedelta(seconds=600)
    await db_session.execute(
        text(
            "UPDATE ct_log_backfill_state "
            "SET claimed_by='old', heartbeat_at=:ts, status='claimed' "
            "WHERE log_source_id=:id"
        ).bindparams(ts=past, id=log_id)
    )

    async with db_session.begin_nested():
        row = await claim_any_eligible_log(
            db_session, worker_id="new", stale_seconds=_STALE_SECONDS
        )

    assert row is not None
    assert row.claimed_by == "new"


# ---------------------------------------------------------------------------
# update_log_progress / mark_log_retrying
# ---------------------------------------------------------------------------


async def test_update_log_progress_advances_checkpoint(
    db_session: AsyncSession,
) -> None:
    """update_log_progress advances checkpoint and sets status."""
    from ctpool.worker_claim import update_log_progress

    log_id = await _insert_log_source(db_session)
    await _ensure(db_session, log_id)

    async with db_session.begin_nested():
        await claim_log_for_worker(
            db_session,
            log_source_id=log_id,
            worker_id="w1",
            stale_seconds=_STALE_SECONDS,
        )

    async with db_session.begin_nested():
        await update_log_progress(
            db_session,
            log_source_id=log_id,
            worker_id="w1",
            checkpoint_index=42_000,
            status="processing",
        )

    result = await db_session.execute(
        text(
            "SELECT last_checkpoint_index, status FROM ct_log_backfill_state "
            "WHERE log_source_id=:id"
        ).bindparams(id=log_id)
    )
    row = result.first()
    assert row is not None
    assert row[0] == 42_000
    assert row[1] == "processing"


async def test_update_log_progress_rejects_other_worker(
    db_session: AsyncSession,
) -> None:
    """update_log_progress only updates rows owned by the given worker."""
    from ctpool.worker_claim import update_log_progress

    log_id = await _insert_log_source(db_session)
    await _ensure(db_session, log_id)

    async with db_session.begin_nested():
        await claim_log_for_worker(
            db_session,
            log_source_id=log_id,
            worker_id="owner",
            stale_seconds=_STALE_SECONDS,
        )

    async with db_session.begin_nested():
        await update_log_progress(
            db_session,
            log_source_id=log_id,
            worker_id="someone-else",
            checkpoint_index=99_999,
            status="processing",
        )

    result = await db_session.execute(
        text(
            "SELECT last_checkpoint_index FROM ct_log_backfill_state "
            "WHERE log_source_id=:id"
        ).bindparams(id=log_id)
    )
    assert result.scalar_one() != 99_999


async def test_mark_log_retrying_does_not_advance_checkpoint(
    db_session: AsyncSession,
) -> None:
    """mark_log_retrying records error and leaves checkpoint untouched."""
    from ctpool.worker_claim import mark_log_retrying, update_log_progress

    log_id = await _insert_log_source(db_session)
    await _ensure(db_session, log_id)

    async with db_session.begin_nested():
        await claim_log_for_worker(
            db_session,
            log_source_id=log_id,
            worker_id="w1",
            stale_seconds=_STALE_SECONDS,
        )
    async with db_session.begin_nested():
        await update_log_progress(
            db_session,
            log_source_id=log_id,
            worker_id="w1",
            checkpoint_index=12_345,
            status="processing",
        )

    async with db_session.begin_nested():
        await mark_log_retrying(
            db_session,
            log_source_id=log_id,
            worker_id="w1",
            error_type="RateLimitError",
            error_message="429 from log",
        )

    result = await db_session.execute(
        text(
            "SELECT last_checkpoint_index, status, last_error_type, "
            "last_error_message FROM ct_log_backfill_state "
            "WHERE log_source_id=:id"
        ).bindparams(id=log_id)
    )
    row = result.first()
    assert row is not None
    assert row[0] == 12_345
    assert row[1] == "retrying"
    assert row[2] == "RateLimitError"
    assert row[3] == "429 from log"
