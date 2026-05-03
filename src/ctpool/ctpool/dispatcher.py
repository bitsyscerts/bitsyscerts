"""Dispatcher: eligibility checks, cursor management, and range claiming.

Exports:
    get_eligible_tail_logs     — Query logs eligible for tail ingestion.
    get_eligible_backfill_logs — Query logs eligible for backfill.
    ensure_tail_cursor         — Get-or-create a tail cursor for a log.
    advance_tail_cursor        — Advance the cursor's next_index.
    create_backfill_ranges     — Partition an index range into work chunks.
    claim_backfill_range       — Atomically claim one pending range (SKIP LOCKED).
    mark_range_complete        — Mark a range as complete.
    mark_range_failed          — Mark a range as failed with a reason.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from ctpool.models.log_backfill_range import CtLogBackfillRange
from ctpool.models.log_source import CtLogSource
from ctpool.models.log_tail_cursor import CtLogTailCursor


async def get_eligible_tail_logs(session: AsyncSession) -> list[CtLogSource]:
    """Return all CT logs eligible for tail ingestion.

    Args:
        session: Active async database session.

    Returns:
        List of :class:`CtLogSource` rows with ``is_eligible_for_tail=True``.
    """
    result = await session.execute(
        select(CtLogSource).where(CtLogSource.is_eligible_for_tail.is_(True))
    )
    return list(result.scalars().all())


async def get_eligible_backfill_logs(session: AsyncSession) -> list[CtLogSource]:
    """Return all CT logs eligible for backfill ingestion.

    Args:
        session: Active async database session.

    Returns:
        List of :class:`CtLogSource` rows with ``is_eligible_for_backfill=True``.
    """
    result = await session.execute(
        select(CtLogSource).where(CtLogSource.is_eligible_for_backfill.is_(True))
    )
    return list(result.scalars().all())


async def ensure_tail_cursor(
    session: AsyncSession,
    log_source_id: uuid.UUID,
) -> CtLogTailCursor:
    """Return the tail cursor for *log_source_id*, creating it if absent.

    Args:
        session:       Active async database session.
        log_source_id: UUID of the CT log.

    Returns:
        Existing or newly-created :class:`CtLogTailCursor`.
    """
    stmt = (
        pg_insert(CtLogTailCursor)
        .values(log_source_id=log_source_id, next_index=0)
        .on_conflict_do_nothing(index_elements=["log_source_id"])
        .returning(CtLogTailCursor)
    )
    result = await session.execute(stmt)
    row = result.scalars().first()
    if row is not None:
        return row

    # Row already existed — fetch it.
    existing = await session.execute(
        select(CtLogTailCursor).where(CtLogTailCursor.log_source_id == log_source_id)
    )
    cursor = existing.scalars().first()
    assert cursor is not None  # noqa: S101  — guaranteed by FK / prior insert
    return cursor


async def advance_tail_cursor(
    session: AsyncSession,
    log_source_id: uuid.UUID,
    next_index: int,
) -> None:
    """Advance the tail cursor's ``next_index`` for *log_source_id*.

    Args:
        session:       Active async database session.
        log_source_id: UUID of the CT log.
        next_index:    New value for ``next_index``.
    """
    await session.execute(
        update(CtLogTailCursor)
        .where(CtLogTailCursor.log_source_id == log_source_id)
        .values(next_index=next_index, updated_at=datetime.now(UTC))
    )


async def create_backfill_ranges(
    session: AsyncSession,
    log_source: CtLogSource,
    start_index: int,
    end_index: int,
    chunk_size: int = 10_000,
) -> int:
    """Partition ``[start_index, end_index]`` into pending backfill work chunks.

    Chunks are of at most *chunk_size* entries.  Each chunk is inserted with
    ``ON CONFLICT DO NOTHING`` so re-running is idempotent (ranges are keyed on
    ``(log_source_id, start_index, end_index)`` via the model's unique
    constraint).

    Args:
        session:     Active async database session.
        log_source:  The CT log being partitioned.
        start_index: First log index (inclusive).
        end_index:   Last log index (inclusive).
        chunk_size:  Maximum entries per chunk.

    Returns:
        Number of range rows inserted.
    """
    # We use explicit chunking and INSERT … ON CONFLICT DO NOTHING
    # so this function is safe to call multiple times.
    # WARNING: loop size can be large for big backfills;
    # batching into bulk inserts is left as a future optimisation.
    created = 0
    current = start_index
    while current <= end_index:
        chunk_end = min(current + chunk_size - 1, end_index)
        stmt = (
            pg_insert(CtLogBackfillRange)
            .values(
                log_source_id=log_source.id,
                start_index=current,
                end_index=chunk_end,
                next_index=current,
                status="pending",
            )
            .on_conflict_do_nothing(
                index_elements=["log_source_id", "start_index", "end_index"],
            )
        )
        await session.execute(stmt)
        created += 1
        current = chunk_end + 1
    return created


async def claim_backfill_range(
    session: AsyncSession,
    log_source_id: uuid.UUID | None,
    worker_id: str,
) -> CtLogBackfillRange | None:
    """Atomically claim a pending backfill range via ``SELECT FOR UPDATE SKIP LOCKED``.

    Args:
        session:       Active async database session (must be inside a transaction).
        log_source_id: Restrict to a specific log, or ``None`` for any log.
        worker_id:     Identifier string stored in ``claimed_by``.

    Returns:
        The claimed :class:`CtLogBackfillRange`, or ``None`` if none are available.
    """
    now = datetime.now(UTC)
    query = (
        select(CtLogBackfillRange)
        .where(CtLogBackfillRange.status == "pending")
        .with_for_update(skip_locked=True)
        .limit(1)
    )
    if log_source_id is not None:
        query = query.where(CtLogBackfillRange.log_source_id == log_source_id)

    result = await session.execute(query)
    row = result.scalars().first()
    if row is None:
        return None

    row.status = "in_progress"
    row.claimed_by = worker_id
    row.claimed_at = now
    row.updated_at = now
    return row


async def mark_range_complete(
    session: AsyncSession,
    range_id: uuid.UUID,
) -> None:
    """Mark a backfill range as complete.

    Args:
        session:  Active async database session.
        range_id: PK of the :class:`CtLogBackfillRange` to update.
    """
    now = datetime.now(UTC)
    await session.execute(
        update(CtLogBackfillRange)
        .where(CtLogBackfillRange.id == range_id)
        .values(status="complete", completed_at=now, updated_at=now)
    )


async def mark_range_failed(
    session: AsyncSession,
    range_id: uuid.UUID,
    reason: str,
) -> None:
    """Mark a backfill range as failed.

    Args:
        session:  Active async database session.
        range_id: PK of the :class:`CtLogBackfillRange` to update.
        reason:   Short human-readable failure reason (sanitized, no credentials).
    """
    now = datetime.now(UTC)
    await session.execute(
        update(CtLogBackfillRange)
        .where(CtLogBackfillRange.id == range_id)
        .values(
            status="failed",
            claimed_by=reason[:1024],
            updated_at=now,
        )
    )
