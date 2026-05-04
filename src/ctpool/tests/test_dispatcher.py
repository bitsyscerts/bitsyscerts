"""Tests for ctpool.dispatcher — eligibility, cursor management, range claiming.

All tests use the real ``ctpool_test`` database via ``db_session``; every test
rolls back automatically.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ctpool.dispatcher import (
    advance_tail_cursor,
    claim_backfill_range,
    create_backfill_ranges,
    ensure_tail_cursor,
    get_eligible_backfill_logs,
    get_eligible_tail_logs,
    has_backfill_ranges,
    mark_range_complete,
    mark_range_failed,
    reset_tail_cursor,
)
from ctpool.models.log_backfill_range import CtLogBackfillRange
from ctpool.models.log_source import CtLogSource
from ctpool.models.log_tail_cursor import CtLogTailCursor

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_source(
    *,
    url: str = "https://ct.example.com/log/",
    log_id: str = "dGVzdA==",
    tail: bool = True,
    backfill: bool = True,
) -> CtLogSource:
    return CtLogSource(
        id=uuid.uuid4(),
        log_id_b64=log_id,
        operator_name="Test Operator",
        description="Test CT Log",
        url=url,
        public_key_b64="a2V5==",
        log_state="usable",
        is_eligible_for_tail=tail,
        is_eligible_for_backfill=backfill,
        source_list="chrome",
        first_seen_at=datetime.now(UTC),
        last_synced_at=datetime.now(UTC),
    )


# ---------------------------------------------------------------------------
# get_eligible_tail_logs
# ---------------------------------------------------------------------------


async def test_get_eligible_tail_logs_returns_eligible(
    db_session: AsyncSession,
) -> None:
    """Only logs with is_eligible_for_tail=True are returned."""
    eligible = _make_source(url="https://tail1.example.com/", log_id="dA==")
    ineligible = _make_source(
        url="https://notail.example.com/",
        log_id="bA==",
        tail=False,
        backfill=False,
    )
    db_session.add(eligible)
    db_session.add(ineligible)
    await db_session.flush()

    logs = await get_eligible_tail_logs(db_session)
    ids = {log.id for log in logs}
    assert eligible.id in ids
    assert ineligible.id not in ids


async def test_get_eligible_tail_logs_empty(db_session: AsyncSession) -> None:
    """Returns empty list when no eligible tail logs exist."""
    source = _make_source(
        url="https://none.example.com/", log_id="bm9uZQ==", tail=False
    )
    db_session.add(source)
    await db_session.flush()
    logs = await get_eligible_tail_logs(db_session)
    ids = {log.id for log in logs}
    assert source.id not in ids


# ---------------------------------------------------------------------------
# get_eligible_backfill_logs
# ---------------------------------------------------------------------------


async def test_get_eligible_backfill_logs_returns_eligible(
    db_session: AsyncSession,
) -> None:
    """Only logs with is_eligible_for_backfill=True are returned."""
    eligible = _make_source(
        url="https://backfill1.example.com/",
        log_id="YmFj",
        tail=False,
        backfill=True,
    )
    ineligible = _make_source(
        url="https://nobackfill.example.com/",
        log_id="bm8=",
        tail=False,
        backfill=False,
    )
    db_session.add(eligible)
    db_session.add(ineligible)
    await db_session.flush()

    logs = await get_eligible_backfill_logs(db_session)
    ids = {log.id for log in logs}
    assert eligible.id in ids
    assert ineligible.id not in ids


# ---------------------------------------------------------------------------
# ensure_tail_cursor
# ---------------------------------------------------------------------------


async def test_ensure_tail_cursor_creates_when_absent(
    db_session: AsyncSession,
) -> None:
    """ensure_tail_cursor inserts a cursor with the supplied init_index."""
    source = _make_source(url="https://cursor1.example.com/", log_id="Y3Vy")
    db_session.add(source)
    await db_session.flush()

    cursor, was_created = await ensure_tail_cursor(
        db_session, source.id, init_index=999
    )

    assert was_created is True
    assert cursor.log_source_id == source.id
    assert cursor.next_index == 999


async def test_ensure_tail_cursor_returns_existing(
    db_session: AsyncSession,
) -> None:
    """ensure_tail_cursor returns the existing row with was_created=False."""
    source = _make_source(url="https://cursor2.example.com/", log_id="Y3Vy2")
    db_session.add(source)
    await db_session.flush()

    c1, created1 = await ensure_tail_cursor(db_session, source.id, init_index=0)
    c2, created2 = await ensure_tail_cursor(db_session, source.id, init_index=0)
    assert c1.id == c2.id
    assert created1 is True
    assert created2 is False


# ---------------------------------------------------------------------------
# advance_tail_cursor
# ---------------------------------------------------------------------------


async def test_advance_tail_cursor_updates_next_index(
    db_session: AsyncSession,
) -> None:
    """advance_tail_cursor sets next_index to the supplied value."""
    source = _make_source(url="https://adv1.example.com/", log_id="YWR2")
    db_session.add(source)
    await db_session.flush()

    cursor, _ = await ensure_tail_cursor(db_session, source.id, init_index=0)
    assert cursor.next_index == 0

    await advance_tail_cursor(db_session, source.id, 500)
    await db_session.flush()

    await db_session.refresh(cursor)
    assert cursor.next_index == 500


# ---------------------------------------------------------------------------
# has_backfill_ranges
# ---------------------------------------------------------------------------


async def test_has_backfill_ranges_false_when_empty(
    db_session: AsyncSession,
) -> None:
    """has_backfill_ranges returns False when no ranges exist for the log."""
    source = _make_source(url="https://hasranges0.example.com/", log_id="aGFzMA==")
    db_session.add(source)
    await db_session.flush()

    assert await has_backfill_ranges(db_session, source.id) is False


async def test_has_backfill_ranges_true_after_seeding(
    db_session: AsyncSession,
) -> None:
    """has_backfill_ranges returns True once ranges have been created."""
    source = _make_source(url="https://hasranges1.example.com/", log_id="aGFzMQ==")
    db_session.add(source)
    await db_session.flush()

    await create_backfill_ranges(
        db_session, source, start_index=0, end_index=9999, chunk_size=10_000
    )
    await db_session.flush()

    assert await has_backfill_ranges(db_session, source.id) is True


# ---------------------------------------------------------------------------
# create_backfill_ranges
# ---------------------------------------------------------------------------


async def test_create_backfill_ranges_creates_chunks(
    db_session: AsyncSession,
) -> None:
    """create_backfill_ranges partitions the range into chunks."""
    source = _make_source(url="https://ranges1.example.com/", log_id="cmFuZ2U=")
    db_session.add(source)
    await db_session.flush()

    count = await create_backfill_ranges(
        db_session, source, start_index=0, end_index=24999, chunk_size=10_000
    )
    await db_session.flush()

    assert count == 3  # [0-9999], [10000-19999], [20000-24999]

    result = await db_session.execute(
        select(CtLogBackfillRange).where(CtLogBackfillRange.log_source_id == source.id)
    )
    rows = result.scalars().all()
    assert len(rows) == 3
    statuses = {row.status for row in rows}
    assert statuses == {"pending"}


async def test_create_backfill_ranges_single_range(
    db_session: AsyncSession,
) -> None:
    """Small range produces exactly one chunk."""
    source = _make_source(url="https://ranges2.example.com/", log_id="cmFuZ2Uy")
    db_session.add(source)
    await db_session.flush()

    count = await create_backfill_ranges(
        db_session, source, start_index=0, end_index=100, chunk_size=10_000
    )
    assert count == 1


async def test_create_backfill_ranges_idempotent(
    db_session: AsyncSession,
) -> None:
    """Calling create_backfill_ranges twice does not duplicate rows
    (ON CONFLICT DO NOTHING)."""
    source = _make_source(url="https://ranges3.example.com/", log_id="cmFuZ2Uz")
    db_session.add(source)
    await db_session.flush()

    await create_backfill_ranges(
        db_session, source, start_index=0, end_index=9999, chunk_size=10_000
    )
    await db_session.flush()
    await create_backfill_ranges(
        db_session, source, start_index=0, end_index=9999, chunk_size=10_000
    )
    await db_session.flush()

    result = await db_session.execute(
        select(CtLogBackfillRange).where(CtLogBackfillRange.log_source_id == source.id)
    )
    rows = result.scalars().all()
    assert len(rows) == 1


async def test_create_backfill_ranges_bulk_insert_exceeds_batch_size(
    db_session: AsyncSession,
) -> None:
    """Ranges exceeding _insert_batch are split across multiple bulk INSERTs."""
    source = _make_source(url="https://ranges4.example.com/", log_id="cmFuZ2U0")
    db_session.add(source)
    await db_session.flush()

    # 600 chunks of 1 entry each; default _insert_batch=500 → 2 INSERT statements
    count = await create_backfill_ranges(
        db_session,
        source,
        start_index=0,
        end_index=599,
        chunk_size=1,
        _insert_batch=500,
    )
    await db_session.flush()

    assert count == 600
    result = await db_session.execute(
        select(CtLogBackfillRange).where(CtLogBackfillRange.log_source_id == source.id)
    )
    rows = result.scalars().all()
    assert len(rows) == 600


# ---------------------------------------------------------------------------
# claim_backfill_range
# ---------------------------------------------------------------------------


async def test_claim_backfill_range_claims_pending(
    db_session: AsyncSession,
) -> None:
    """claim_backfill_range returns a range and marks it in_progress."""
    source = _make_source(url="https://claim1.example.com/", log_id="Y2xhaW0=")
    db_session.add(source)
    await db_session.flush()

    await create_backfill_ranges(
        db_session, source, start_index=0, end_index=9999, chunk_size=10_000
    )
    await db_session.flush()

    claimed = await claim_backfill_range(db_session, source.id, "worker-1")
    assert claimed is not None
    assert claimed.status == "in_progress"
    assert claimed.claimed_by == "worker-1"
    assert claimed.claimed_at is not None


async def test_claim_backfill_range_returns_none_when_empty(
    db_session: AsyncSession,
) -> None:
    """Returns None when no pending ranges exist."""
    claimed = await claim_backfill_range(db_session, uuid.uuid4(), "worker-1")
    assert claimed is None


async def test_claim_backfill_range_with_none_log_source(
    db_session: AsyncSession,
) -> None:
    """claim_backfill_range(log_source_id=None) claims from any log."""
    source = _make_source(url="https://claim2.example.com/", log_id="Y2xhaW0y")
    db_session.add(source)
    await db_session.flush()

    await create_backfill_ranges(
        db_session, source, start_index=0, end_index=9999, chunk_size=10_000
    )
    await db_session.flush()

    claimed = await claim_backfill_range(db_session, None, "worker-any")
    assert claimed is not None
    assert claimed.status == "in_progress"


# ---------------------------------------------------------------------------
# mark_range_complete
# ---------------------------------------------------------------------------


async def test_mark_range_complete_sets_status(
    db_session: AsyncSession,
) -> None:
    """mark_range_complete sets status='complete' and completed_at."""
    source = _make_source(url="https://done1.example.com/", log_id="ZG9uZQ==")
    db_session.add(source)
    await db_session.flush()

    await create_backfill_ranges(
        db_session, source, start_index=0, end_index=9999, chunk_size=10_000
    )
    await db_session.flush()

    claimed = await claim_backfill_range(db_session, source.id, "worker-1")
    assert claimed is not None

    await mark_range_complete(db_session, claimed.id)
    await db_session.flush()

    await db_session.refresh(claimed)
    assert claimed.status == "complete"
    assert claimed.completed_at is not None


# ---------------------------------------------------------------------------
# mark_range_failed
# ---------------------------------------------------------------------------


async def test_mark_range_failed_sets_status(
    db_session: AsyncSession,
) -> None:
    """mark_range_failed sets status='failed' and stores reason."""
    source = _make_source(url="https://fail1.example.com/", log_id="ZmFpbA==")
    db_session.add(source)
    await db_session.flush()

    await create_backfill_ranges(
        db_session, source, start_index=0, end_index=9999, chunk_size=10_000
    )
    await db_session.flush()

    claimed = await claim_backfill_range(db_session, source.id, "worker-1")
    assert claimed is not None

    await mark_range_failed(db_session, claimed.id, "timeout error")
    await db_session.flush()

    await db_session.refresh(claimed)
    assert claimed.status == "failed"
    assert "timeout error" in (claimed.claimed_by or "")


# ---------------------------------------------------------------------------
# reset_tail_cursor
# ---------------------------------------------------------------------------


async def test_reset_tail_cursor_returns_old_value(
    db_session: AsyncSession,
) -> None:
    """reset_tail_cursor overwrites next_index and returns the previous value."""
    source = _make_source(url="https://reset1.example.com/", log_id="cmVzZXQ=")
    db_session.add(source)
    await db_session.flush()

    await ensure_tail_cursor(db_session, source.id, init_index=500)
    await db_session.flush()

    old = await reset_tail_cursor(db_session, source.id, 1_000_000)
    await db_session.flush()

    assert old == 500

    result = await db_session.execute(
        select(CtLogTailCursor).where(CtLogTailCursor.log_source_id == source.id)
    )
    cursor = result.scalars().first()
    assert cursor is not None
    assert cursor.next_index == 1_000_000


async def test_reset_tail_cursor_raises_when_no_cursor(
    db_session: AsyncSession,
) -> None:
    """reset_tail_cursor raises ValueError when no cursor row exists."""
    import pytest

    source = _make_source(url="https://reset2.example.com/", log_id="cmVzZXQy")
    db_session.add(source)
    await db_session.flush()

    # No cursor created — reset should fail loudly.
    with pytest.raises(ValueError, match="No tail cursor found"):
        await reset_tail_cursor(db_session, source.id, 999)
