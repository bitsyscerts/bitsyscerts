"""Dispatcher: eligibility checks, cursor management, and range claiming.

Exports:
    get_eligible_tail_logs        — Query logs eligible for tail ingestion.
    get_eligible_backfill_logs    — Query logs eligible for backfill.
    try_claim_tail_log            — Acquire a transaction-scoped lease for one log.
    ensure_tail_cursor            — Get-or-create a tail cursor for a log (caller
                                    supplies init_index; returns (cursor, was_created)).
    advance_tail_cursor           — Advance the cursor's next_index.
    reset_tail_cursor             — Overwrite next_index and return the old value.
    has_backfill_ranges           — Return True if any ranges already exist for a log.
    create_backfill_ranges        — Partition an index range into work chunks.
    claim_backfill_range          — Atomically claim one pending range (SKIP LOCKED).
    update_range_heartbeat        — Refresh heartbeat_at for an in-progress range.
    reap_stale_backfill_claims    — Reset in_progress ranges with stale heartbeats.
    mark_range_complete           — Mark a range as complete.
    mark_range_failed             — Mark a range as failed with a reason.
    mark_range_pending            — Return a claimed range back to pending.
"""

from __future__ import annotations

import inspect
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import exists, func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from ctpool.models.log_backfill_range import CtLogBackfillRange
from ctpool.models.log_source import CtLogSource
from ctpool.models.log_tail_cursor import CtLogTailCursor


def _advisory_key_for_uuid(value: uuid.UUID) -> int:
    """Return a deterministic signed int64 advisory-lock key for *value*."""
    return int.from_bytes(value.bytes[:8], byteorder="big", signed=True)


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
    *,
    init_index: int,
) -> tuple[CtLogTailCursor, bool]:
    """Return the tail cursor for *log_source_id*, creating it if absent.

    Args:
        session:       Active async database session.
        log_source_id: UUID of the CT log.
        init_index:    ``next_index`` value to use when inserting a new cursor.
                       Ignored when a cursor already exists.

    Returns:
        ``(cursor, was_created)`` — the cursor and ``True`` when newly inserted,
        ``False`` when the row already existed.
    """
    stmt = (
        pg_insert(CtLogTailCursor)
        .values(log_source_id=log_source_id, next_index=init_index)
        .on_conflict_do_nothing(index_elements=["log_source_id"])
        .returning(CtLogTailCursor)
    )
    result = await session.execute(stmt)
    row = result.scalars().first()
    if row is not None:
        return row, True

    # Row already existed — fetch it.
    existing = await session.execute(
        select(CtLogTailCursor).where(CtLogTailCursor.log_source_id == log_source_id)
    )
    cursor = existing.scalars().first()
    assert cursor is not None  # noqa: S101  — guaranteed by FK / prior insert
    return cursor, False


async def reset_tail_cursor(
    session: AsyncSession,
    log_source_id: uuid.UUID,
    new_index: int,
) -> int:
    """Overwrite the tail cursor's ``next_index`` and return the previous value.

    Args:
        session:       Active async database session.
        log_source_id: UUID of the CT log.
        new_index:     Replacement value for ``next_index``.

    Returns:
        The old ``next_index`` value before the reset.

    Raises:
        ValueError: If no tail cursor row exists for *log_source_id*.
    """
    existing = await session.execute(
        select(CtLogTailCursor).where(CtLogTailCursor.log_source_id == log_source_id)
    )
    cursor = existing.scalars().first()
    if cursor is None:
        raise ValueError(f"No tail cursor found for log_source_id={log_source_id}")
    old_index: int = cursor.next_index
    await session.execute(
        update(CtLogTailCursor)
        .where(CtLogTailCursor.log_source_id == log_source_id)
        .values(next_index=new_index, updated_at=datetime.now(UTC))
    )
    return old_index


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


async def try_claim_tail_log(
    session: AsyncSession,
    log_source_id: uuid.UUID,
) -> bool:
    """Try to acquire a transaction-scoped advisory lock for one tail log.

    Returns ``True`` when this transaction owns the lease and should process
    the log, otherwise ``False``.
    """
    key = _advisory_key_for_uuid(log_source_id)
    result = await session.execute(select(func.pg_try_advisory_xact_lock(key)))
    claimed = result.scalar()
    if inspect.isawaitable(claimed):
        claimed = await claimed
    return bool(claimed)


async def has_backfill_ranges(
    session: AsyncSession,
    log_source_id: uuid.UUID,
) -> bool:
    """Return True if any backfill ranges exist for *log_source_id*.

    Used to skip re-seeding on restarts without making an HTTP call.

    Args:
        session:       Active async database session.
        log_source_id: UUID of the CT log.

    Returns:
        ``True`` when at least one range row exists for this log.
    """
    result = await session.execute(
        select(exists().where(CtLogBackfillRange.log_source_id == log_source_id))
    )
    has_rows = result.scalar()
    if inspect.isawaitable(has_rows):
        has_rows = await has_rows
    return bool(has_rows)


async def create_backfill_ranges(
    session: AsyncSession,
    log_source: CtLogSource,
    start_index: int,
    end_index: int,
    chunk_size: int = 10_000,
    _insert_batch: int = 500,
) -> int:
    """Partition ``[start_index, end_index]`` into pending backfill work chunks.

    Chunks are of at most *chunk_size* entries.  Rows are inserted in bulk
    batches of ``_insert_batch`` chunks per SQL statement so seeding a large
    log (100M+ entries) takes seconds rather than minutes.  Each insert uses
    ``ON CONFLICT DO NOTHING`` so re-running is idempotent.

    Args:
        session:       Active async database session.
        log_source:    The CT log being partitioned.
        start_index:   First log index (inclusive).
        end_index:     Last log index (inclusive).
        chunk_size:    Maximum entries per chunk (default 10,000).
        _insert_batch: Number of chunk rows per bulk INSERT (default 500).

    Returns:
        Number of range rows inserted.
    """
    # Build the full list of (start, end) pairs first, then bulk-insert.
    pairs: list[tuple[int, int]] = []
    current = start_index
    while current <= end_index:
        chunk_end = min(current + chunk_size - 1, end_index)
        pairs.append((current, chunk_end))
        current = chunk_end + 1

    created = 0
    for i in range(0, len(pairs), _insert_batch):
        batch = pairs[i : i + _insert_batch]
        values = [
            {
                "log_source_id": log_source.id,
                "start_index": s,
                "end_index": e,
                "next_index": s,
                "status": "pending",
            }
            for s, e in batch
        ]
        stmt = (
            pg_insert(CtLogBackfillRange)
            .values(values)
            .on_conflict_do_nothing(
                index_elements=["log_source_id", "start_index", "end_index"],
            )
        )
        await session.execute(stmt)
        created += len(batch)
    return created


async def claim_backfill_range(
    session: AsyncSession,
    log_source_id: uuid.UUID | None,
    worker_id: str,
    excluded_log_source_ids: set[uuid.UUID] | None = None,
) -> CtLogBackfillRange | None:
    """Atomically claim a pending backfill range via ``SELECT FOR UPDATE SKIP LOCKED``.

    Args:
        session:       Active async database session (must be inside a transaction).
        log_source_id: Restrict to a specific log, or ``None`` for any log.
        worker_id:     Identifier string stored in ``claimed_by``.
        excluded_log_source_ids: Optional set of logs to skip (e.g. per-log
                                 rate-limit cooldown).

    Returns:
        The claimed :class:`CtLogBackfillRange`, or ``None`` if none are available.
    """
    now = datetime.now(UTC)
    target_log_source_id = log_source_id

    if target_log_source_id is None:
        log_query = select(CtLogBackfillRange.log_source_id).where(
            CtLogBackfillRange.status == "pending"
        )
        if excluded_log_source_ids:
            log_query = log_query.where(
                ~CtLogBackfillRange.log_source_id.in_(excluded_log_source_ids)
            )
        log_query = log_query.group_by(CtLogBackfillRange.log_source_id).order_by(
            func.random()
        )
        log_query = log_query.limit(1)
        target_log_source_id = (await session.execute(log_query)).scalar_one_or_none()
        if target_log_source_id is None:
            return None

    if (
        excluded_log_source_ids
        and log_source_id is not None
        and log_source_id in excluded_log_source_ids
    ):
        return None

    query = (
        select(CtLogBackfillRange)
        .where(CtLogBackfillRange.status == "pending")
        .where(CtLogBackfillRange.log_source_id == target_log_source_id)
        .order_by(CtLogBackfillRange.start_index.desc())
        .with_for_update(skip_locked=True)
        .limit(1)
    )

    result = await session.execute(query)
    row = result.scalars().first()
    if row is None:
        return None

    row.status = "in_progress"
    row.claimed_by = worker_id
    row.claimed_at = now
    row.heartbeat_at = now
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


async def mark_range_pending(
    session: AsyncSession,
    range_id: uuid.UUID,
) -> None:
    """Return a claimed/failed backfill range to pending state."""
    now = datetime.now(UTC)
    await session.execute(
        update(CtLogBackfillRange)
        .where(CtLogBackfillRange.id == range_id)
        .values(
            status="pending",
            claimed_by=None,
            claimed_at=None,
            heartbeat_at=None,
            updated_at=now,
        )
    )


async def update_range_heartbeat(
    session: AsyncSession,
    range_id: uuid.UUID,
) -> None:
    """Refresh ``heartbeat_at`` for an in-progress backfill range.

    Should be called periodically by the backfill worker so the stale-claim
    reaper does not reset a range that is still being actively processed.

    Args:
        session:  Active async database session (must be inside a transaction).
        range_id: PK of the :class:`CtLogBackfillRange` to update.
    """
    now = datetime.now(UTC)
    await session.execute(
        update(CtLogBackfillRange)
        .where(CtLogBackfillRange.id == range_id)
        .where(CtLogBackfillRange.status == "in_progress")
        .values(heartbeat_at=now, updated_at=now)
    )


async def reap_stale_backfill_claims(
    session: AsyncSession,
    claim_timeout_seconds: int,
) -> list[CtLogBackfillRange]:
    """Reset in_progress ranges whose heartbeat has not been refreshed recently.

    A range is considered stale when
    ``COALESCE(heartbeat_at, claimed_at) < now() - timeout``.
    Stale ranges are returned to ``pending`` status so they can be
    re-claimed.  ``next_index`` is preserved so partial progress is retained.

    Args:
        session:               Active async database session (must be inside a
                               transaction).
        claim_timeout_seconds: Seconds of silence before a claim is declared stale.

    Returns:
        List of :class:`CtLogBackfillRange` rows that were reset to pending.
    """
    cutoff = datetime.now(UTC) - timedelta(seconds=claim_timeout_seconds)
    stmt = (
        update(CtLogBackfillRange)
        .where(CtLogBackfillRange.status == "in_progress")
        .where(
            func.coalesce(
                CtLogBackfillRange.heartbeat_at, CtLogBackfillRange.claimed_at
            )
            < cutoff
        )
        .values(
            status="pending",
            claimed_by=None,
            claimed_at=None,
            heartbeat_at=None,
            updated_at=func.now(),
        )
        .returning(
            CtLogBackfillRange.id,
            CtLogBackfillRange.log_source_id,
            CtLogBackfillRange.start_index,
            CtLogBackfillRange.end_index,
            CtLogBackfillRange.next_index,
        )
    )
    result = await session.execute(stmt)
    return list(result.all())
