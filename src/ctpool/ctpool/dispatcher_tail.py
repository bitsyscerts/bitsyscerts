"""Tail-log dispatcher: eligibility queries, cursor management, and lease claiming.

# NOTE (201-500 line warning zone): This module consolidates all tail-related
# dispatcher concerns: eligibility queries, cursor management, the deprecated
# advisory-lock claim, and the new persistent-lease functions.  Splitting
# further would scatter closely related lease operations across multiple files
# with no cohesion benefit.  Resolve if any single concern group exceeds 100
# lines on its own (e.g. extract a lease_manager.py for the 5 lease functions).

Exports:
    get_eligible_tail_logs   — Query logs eligible for tail ingestion.
    ensure_tail_cursor       — Get-or-create a tail cursor for a log.
    advance_tail_cursor      — Advance the cursor's next_index.
    reset_tail_cursor        — Overwrite next_index and return the old value.
    try_claim_tail_log       — (Deprecated) Advisory-lock claim; use claim_tail_log.
    claim_tail_log           — Atomically claim a persistent tail lease.
    release_tail_log         — Release a tail lease held by this worker.
    heartbeat_tail_lease     — Refresh heartbeat_at for an active lease.
    reap_stale_tail_leases   — Reset leases whose heartbeat has expired.
"""

from __future__ import annotations

import inspect
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from ctpool.models.log_source import CtLogSource
from ctpool.models.log_tail_cursor import CtLogTailCursor
from ctpool.models.log_tail_lease import CtLogTailLease


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

    .. deprecated::
        Use :func:`claim_tail_log` instead.  This advisory-lock variant
        releases the lock at COMMIT, before the actual batch processing begins,
        allowing a second worker to claim the same log simultaneously.

    Returns ``True`` when this transaction owns the lease, otherwise ``False``.
    """
    key = _advisory_key_for_uuid(log_source_id)
    result = await session.execute(select(func.pg_try_advisory_xact_lock(key)))
    claimed = result.scalar()
    if inspect.isawaitable(claimed):
        claimed = await claimed
    return bool(claimed)


async def claim_tail_log(
    session: AsyncSession,
    log_source_id: uuid.UUID,
    worker_id: str,
    stale_seconds: int,
) -> bool:
    """Atomically claim a persistent tail lease for *log_source_id*.

    Upserts a row in ``ct_log_tail_leases``.  The claim succeeds only when
    ``claimed_by`` is NULL or the existing lease is stale (heartbeat older
    than *stale_seconds*).  Returns ``True`` when this worker holds the lease
    after the call.

    Args:
        session:       Active async database session (must be inside a transaction).
        log_source_id: UUID of the CT log to claim.
        worker_id:     Caller's ``hostname:PID`` identity string.
        stale_seconds: Seconds of silence before an existing lease is considered stale.

    Returns:
        ``True`` when the lease was claimed or was already held by *worker_id*.
    """
    now = datetime.now(UTC)
    cutoff = now - timedelta(seconds=stale_seconds)
    stmt = (
        pg_insert(CtLogTailLease)
        .values(
            log_source_id=log_source_id,
            claimed_by=worker_id,
            claimed_at=now,
            heartbeat_at=now,
        )
        .on_conflict_do_update(
            index_elements=["log_source_id"],
            set_={
                "claimed_by": worker_id,
                "claimed_at": now,
                "heartbeat_at": now,
            },
            where=(
                (CtLogTailLease.claimed_by.is_(None))
                | (CtLogTailLease.claimed_by == worker_id)
                | (CtLogTailLease.heartbeat_at < cutoff)
            ),
        )
        .returning(CtLogTailLease.claimed_by)
    )
    result = await session.execute(stmt)
    row = result.first()
    return row is not None and row[0] == worker_id


async def release_tail_log(
    session: AsyncSession,
    log_source_id: uuid.UUID,
    worker_id: str,
) -> None:
    """Release the tail lease held by *worker_id* for *log_source_id*.

    No-op when the lease row does not exist or is held by a different worker.

    Args:
        session:       Active async database session (must be inside a transaction).
        log_source_id: UUID of the CT log to release.
        worker_id:     Must match the current ``claimed_by`` to take effect.
    """
    await session.execute(
        update(CtLogTailLease)
        .where(CtLogTailLease.log_source_id == log_source_id)
        .where(CtLogTailLease.claimed_by == worker_id)
        .values(claimed_by=None, claimed_at=None, heartbeat_at=None)
    )


async def heartbeat_tail_lease(
    session: AsyncSession,
    log_source_id: uuid.UUID,
    worker_id: str,
) -> None:
    """Update ``heartbeat_at`` to now for this worker's active lease.

    No-op when the lease row does not exist or is held by a different worker.

    Args:
        session:       Active async database session (must be inside a transaction).
        log_source_id: UUID of the CT log.
        worker_id:     Must match the current ``claimed_by`` to take effect.
    """
    await session.execute(
        update(CtLogTailLease)
        .where(CtLogTailLease.log_source_id == log_source_id)
        .where(CtLogTailLease.claimed_by == worker_id)
        .values(heartbeat_at=datetime.now(UTC))
    )


async def reap_stale_tail_leases(
    session: AsyncSession,
    stale_seconds: int,
) -> int:
    """Reset tail leases whose heartbeat has expired.

    Leases with ``heartbeat_at < now() - stale_seconds`` are cleared so
    another worker can claim the log.  Returns the number of rows reset.

    Args:
        session:       Active async database session (must be inside a transaction).
        stale_seconds: Age threshold in seconds.

    Returns:
        Number of leases reset.
    """
    cutoff = datetime.now(UTC) - timedelta(seconds=stale_seconds)
    result = await session.execute(
        update(CtLogTailLease)
        .where(CtLogTailLease.claimed_by.isnot(None))
        .where(CtLogTailLease.heartbeat_at < cutoff)
        .values(claimed_by=None, claimed_at=None, heartbeat_at=None)
    )
    return result.rowcount
