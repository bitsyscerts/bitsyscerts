"""Backfill dispatcher: range creation, claiming, and lifecycle management.

# NOTE (201-500 line warning zone): This module consolidates all backfill range
# dispatcher concerns.  The create/claim/heartbeat/reap/mark operations are
# tightly coupled through CtLogBackfillRange state transitions; splitting them
# would require passing row objects across module boundaries.  Resolve if any
# single state-transition group exceeds 100 lines on its own.

Exports:
    get_eligible_backfill_logs  — Query logs eligible for backfill ingestion.
    has_backfill_ranges         — Return True if any ranges exist for a log.
    create_backfill_ranges      — Partition an index range into work chunks.
    claim_backfill_range        — Atomically claim a pending range (SKIP LOCKED).
    update_range_heartbeat      — Refresh heartbeat_at for an in-progress range.
    reap_stale_backfill_claims  — Reset in_progress ranges with stale heartbeats.
    mark_range_complete         — Mark a range as complete.
    mark_range_failed           — Mark a range as failed with a reason.
    mark_range_pending          — Return a claimed range back to pending.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import exists, func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from ctpool.models.log_backfill_range import CtLogBackfillRange
from ctpool.models.log_source import CtLogSource


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


async def has_backfill_ranges(
    session: AsyncSession,
    log_source_id: uuid.UUID,
) -> bool:
    """Return True if any backfill ranges exist for *log_source_id*.

    Args:
        session:       Active async database session.
        log_source_id: UUID of the CT log.

    Returns:
        ``True`` when at least one range row exists for this log.
    """
    import inspect

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

    Inserts rows in bulk batches using ``ON CONFLICT DO NOTHING`` so
    re-running is idempotent.

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
    # NOTE (21-50 lines): sequential pair generation + chunked INSERT cannot
    # be cleanly split without passing a list between helpers.
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
        excluded_log_source_ids: Optional set of logs to skip.

    Returns:
        The claimed :class:`CtLogBackfillRange`, or ``None`` if none are available.
    """
    # NOTE (21-50 lines): two-phase "pick log then claim range" query cannot
    # be simplified without losing the SKIP LOCKED guarantee.
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
        log_query = (
            log_query.group_by(CtLogBackfillRange.log_source_id)
            .order_by(func.random())
            .limit(1)
        )
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


async def mark_range_complete(session: AsyncSession, range_id: uuid.UUID) -> None:
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
        .values(status="failed", claimed_by=reason[:1024], updated_at=now)
    )


async def mark_range_pending(session: AsyncSession, range_id: uuid.UUID) -> None:
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

    A range is stale when ``COALESCE(heartbeat_at, claimed_at) < now() - timeout``.

    Args:
        session:               Active async database session (inside a transaction).
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
