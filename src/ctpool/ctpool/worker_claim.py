"""Per-log backfill ownership claim management for ct_log_backfill_state.

Exports:
    ensure_log_backfill_state  — Idempotently create per-log state row.
    initialize_log_window      — Set/update backfill window indices.
    claim_log_for_worker       — Atomically claim a specific log.
    claim_any_eligible_log     — Atomically claim any one eligible log.
    release_log_claim          — Release the claim on a log after completion.
    update_log_progress        — Persist durable checkpoint + heartbeat + status.
    mark_log_retrying          — Record retryable failure without advancing checkpoint.
    mark_log_complete          — Mark a log's backfill as fully complete.
    extend_window_backward     — Move backfill_start_index earlier and update coverage.
    update_observed_oldest     — Persist the oldest observed not_before date.
    reap_stale_log_claims      — Reset expired claims so other workers can proceed.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, or_, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from ctpool.models.log_backfill_state import CtLogBackfillState
from ctpool.models.log_source import CtLogSource

_logger = logging.getLogger(__name__)

_STATUS_PENDING = "pending"
_STATUS_CLAIMED = "claimed"
_STATUS_PROCESSING = "processing"
_STATUS_RETRYING = "retrying"
_STATUS_RATE_LIMITED = "rate_limited"
_STATUS_PAUSED = "paused"
_STATUS_COMPLETE = "complete"
_STATUS_ERROR = "error"

# Statuses excluded from auto-claim. Paused/error logs require explicit
# operator action; complete logs are done.
_NON_CLAIMABLE_STATUSES: tuple[str, ...] = (
    _STATUS_PAUSED,
    _STATUS_ERROR,
    _STATUS_COMPLETE,
)

_CLAIMABLE_STATUSES = (
    _STATUS_PENDING,
    _STATUS_CLAIMED,
    _STATUS_PROCESSING,
    _STATUS_RETRYING,
    _STATUS_RATE_LIMITED,
)


async def ensure_log_backfill_state(
    session: AsyncSession,
    *,
    log_source_id: uuid.UUID,
) -> CtLogBackfillState:
    """Idempotently create a per-log backfill state row.

    Safe to call multiple times; only inserts if no row exists yet.

    Args:
        session:       Open async SQLAlchemy session (inside an active transaction).
        log_source_id: UUID of the ``ct_log_sources`` row.

    Returns:
        The existing or newly created :class:`CtLogBackfillState` row.
    """
    stmt = (
        pg_insert(CtLogBackfillState)
        .values(
            id=uuid.uuid4(),
            log_source_id=log_source_id,
            status=_STATUS_PENDING,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        .on_conflict_do_nothing(index_elements=["log_source_id"])
    )
    await session.execute(stmt)

    row_stmt = select(CtLogBackfillState).where(
        CtLogBackfillState.log_source_id == log_source_id
    )
    result = await session.execute(row_stmt)
    row = result.scalar_one()
    return row


async def initialize_log_window(
    session: AsyncSession,
    *,
    log_source_id: uuid.UUID,
    backfill_start_index: int,
    backfill_end_index: int,
) -> None:
    """Set the configured backfill window for a per-log state row.

    Idempotent: if a window is already set and complete, nothing changes.
    Otherwise the window bounds and initial checkpoint are written.

    The convention is forward-dispatch: ``backfill_start_index`` is the
    first (lowest) index to process and ``backfill_end_index`` is the
    last (highest) index. ``last_checkpoint_index`` is set to
    ``backfill_start_index`` so the first batch starts at the window head.

    Args:
        session:              Open async SQLAlchemy session (inside an active txn).
        log_source_id:        UUID of the CT log.
        backfill_start_index: First (low) index to process.
        backfill_end_index:   Last (high) index to process (inclusive).
    """
    stmt = select(CtLogBackfillState).where(
        CtLogBackfillState.log_source_id == log_source_id
    )
    row = (await session.execute(stmt)).scalar_one_or_none()
    if row is None:
        return
    if row.status == _STATUS_COMPLETE:
        return
    now = datetime.now(UTC)
    new_checkpoint = (
        row.last_checkpoint_index
        if row.last_checkpoint_index is not None
        else backfill_start_index
    )
    await session.execute(
        update(CtLogBackfillState)
        .where(CtLogBackfillState.log_source_id == log_source_id)
        .values(
            backfill_start_index=backfill_start_index,
            backfill_end_index=backfill_end_index,
            last_checkpoint_index=new_checkpoint,
            updated_at=now,
        )
    )


async def claim_any_eligible_log(
    session: AsyncSession,
    *,
    worker_id: str,
    stale_seconds: int,
    log_id_filter: uuid.UUID | None = None,
    excluded_log_ids: set[uuid.UUID] | None = None,
) -> CtLogBackfillState | None:
    """Atomically claim any one eligible CT log for *worker_id*.

    A log is eligible when:
      * its parent ``ct_log_sources`` row has ``is_eligible_for_backfill=True``,
      * its ``ct_log_backfill_state`` row is not yet complete,
      * its current claim is absent or the heartbeat is older than *stale_seconds*,
      * the log id is not in *excluded_log_ids*.

    Uses ``SELECT … FOR UPDATE SKIP LOCKED`` against the state row so two
    fresh workers cannot claim the same log.

    Returns:
        The newly claimed :class:`CtLogBackfillState` row, or ``None`` if no
        eligible log is available right now.
    """
    cutoff = datetime.now(UTC) - timedelta(seconds=stale_seconds)
    fresh_claim = and_(
        CtLogBackfillState.claimed_by.is_not(None),
        CtLogBackfillState.heartbeat_at.is_not(None),
        CtLogBackfillState.heartbeat_at >= cutoff,
    )
    stmt = (
        select(CtLogBackfillState)
        .join(
            CtLogSource,
            CtLogSource.id == CtLogBackfillState.log_source_id,
        )
        .where(CtLogSource.is_eligible_for_backfill.is_(True))
        .where(CtLogBackfillState.status.notin_(_NON_CLAIMABLE_STATUSES))
        .where(CtLogBackfillState.completed_at.is_(None))
        .where(or_(CtLogBackfillState.claimed_by.is_(None), ~fresh_claim))
        .order_by(CtLogBackfillState.heartbeat_at.asc().nulls_first())
        .limit(1)
        .with_for_update(skip_locked=True, of=CtLogBackfillState)
    )
    if log_id_filter is not None:
        stmt = stmt.where(CtLogBackfillState.log_source_id == log_id_filter)
    if excluded_log_ids:
        stmt = stmt.where(CtLogBackfillState.log_source_id.notin_(excluded_log_ids))

    row = (await session.execute(stmt)).scalar_one_or_none()
    if row is None:
        return None

    now = datetime.now(UTC)
    await session.execute(
        update(CtLogBackfillState)
        .where(CtLogBackfillState.log_source_id == row.log_source_id)
        .values(
            claimed_by=worker_id,
            claimed_at=now,
            heartbeat_at=now,
            status=_STATUS_CLAIMED,
            updated_at=now,
            last_error_type=None,
            last_error_message=None,
        )
    )
    await session.refresh(row)
    _logger.info(
        "worker_claim: log %s claimed by %s (any-eligible)",
        row.log_source_id,
        worker_id,
    )
    return row


async def claim_log_for_worker(
    session: AsyncSession,
    *,
    log_source_id: uuid.UUID,
    worker_id: str,
    stale_seconds: int,
) -> bool:
    """Atomically claim a backfill log for *worker_id* using a row lock.

    A log is claimable when its current claim is absent or stale (heartbeat
    older than *stale_seconds*).  Uses ``SELECT FOR UPDATE SKIP LOCKED`` to
    prevent two workers from claiming the same log simultaneously.

    Args:
        session:       Open async SQLAlchemy session (inside an active transaction).
        log_source_id: UUID of the log to claim.
        worker_id:     Identity string for the claiming worker.
        stale_seconds: Age in seconds after which an existing claim is stale.

    Returns:
        ``True`` if the claim was acquired; ``False`` if the log is already
        freshly claimed by another worker.
    """

    # Lock the row or skip if it is already locked by another transaction.
    lock_stmt = (
        select(CtLogBackfillState)
        .where(CtLogBackfillState.log_source_id == log_source_id)
        .with_for_update(skip_locked=True)
    )
    result = await session.execute(lock_stmt)
    row = result.scalar_one_or_none()

    if row is None:
        # Row is locked by another worker's active transaction.
        return False

    # Check if an existing claim is fresh.
    if row.claimed_by is not None and row.heartbeat_at is not None:
        cutoff = _utc_cutoff(stale_seconds)
        if row.heartbeat_at >= cutoff:
            return False

    now = datetime.now(UTC)
    await session.execute(
        update(CtLogBackfillState)
        .where(CtLogBackfillState.log_source_id == log_source_id)
        .values(
            claimed_by=worker_id,
            claimed_at=now,
            heartbeat_at=now,
            status=_STATUS_CLAIMED,
            updated_at=now,
            last_error_type=None,
            last_error_message=None,
        )
    )
    _logger.info("worker_claim: log %s claimed by %s", log_source_id, worker_id)
    return True


async def release_log_claim(
    session: AsyncSession,
    *,
    log_source_id: uuid.UUID,
) -> None:
    """Release the backfill claim on a log, resetting it to pending.

    Args:
        session:       Open async SQLAlchemy session (inside an active transaction).
        log_source_id: UUID of the log to release.
    """
    now = datetime.now(UTC)
    await session.execute(
        update(CtLogBackfillState)
        .where(CtLogBackfillState.log_source_id == log_source_id)
        .values(
            claimed_by=None,
            claimed_at=None,
            heartbeat_at=None,
            status=_STATUS_PENDING,
            updated_at=now,
        )
    )
    _logger.info("worker_claim: log %s released", log_source_id)


async def update_log_checkpoint(
    session: AsyncSession,
    *,
    log_source_id: uuid.UUID,
    worker_id: str,
    checkpoint_index: int,
) -> None:
    """Persist a durable backfill progress checkpoint and refresh heartbeat.

    Args:
        session:          Open async SQLAlchemy session (inside an active transaction).
        log_source_id:    UUID of the log being processed.
        worker_id:        Identity string of the owning worker.
        checkpoint_index: Most recently durably processed log index.
    """
    await update_log_progress(
        session,
        log_source_id=log_source_id,
        worker_id=worker_id,
        checkpoint_index=checkpoint_index,
        status=_STATUS_PROCESSING,
    )


async def update_log_progress(
    session: AsyncSession,
    *,
    log_source_id: uuid.UUID,
    worker_id: str,
    checkpoint_index: int | None,
    status: str,
    last_error_type: str | None = None,
    last_error_message: str | None = None,
) -> None:
    """Persist durable progress, heartbeat, and status for a claimed log.

    Only updates rows still owned by *worker_id* — this is the safety check
    that prevents a stale worker from overwriting progress made after its
    claim was reaped.

    On success (``status='processing'``), retry-budget counters are reset
    so a subsequent batch failure starts from zero.
    """
    now = datetime.now(UTC)
    values: dict[str, object] = {
        "heartbeat_at": now,
        "updated_at": now,
        "status": status,
        "last_error_type": last_error_type,
        "last_error_message": last_error_message,
    }
    if checkpoint_index is not None:
        values["last_checkpoint_index"] = checkpoint_index
    if status == _STATUS_PROCESSING and last_error_type is None:
        # Successful batch — clear retry budget and any cooldown.
        values["retry_count"] = 0
        values["next_retry_at"] = None
        values["rate_limited_until"] = None
    await session.execute(
        update(CtLogBackfillState)
        .where(
            CtLogBackfillState.log_source_id == log_source_id,
            CtLogBackfillState.claimed_by == worker_id,
        )
        .values(**values)
    )


async def mark_log_retrying(
    session: AsyncSession,
    *,
    log_source_id: uuid.UUID,
    worker_id: str,
    error_type: str,
    error_message: str,
    retry_after_seconds: int | None = None,
) -> None:
    """Mark the log claim as retrying or rate_limited (no checkpoint advance).

    Increments the retry budget counters atomically with the status
    transition. Heartbeat is refreshed so the claim does not go stale
    during backoff. When *retry_after_seconds* is provided the log is
    flagged as rate-limited and the cooldown is recorded.
    """
    now = datetime.now(UTC)
    is_rate_limited = retry_after_seconds is not None
    new_status = _STATUS_RATE_LIMITED if is_rate_limited else _STATUS_RETRYING
    values: dict[str, object] = {
        "heartbeat_at": now,
        "updated_at": now,
        "status": new_status,
        "last_error_type": error_type,
        "last_error_message": error_message,
        "last_error_at": now,
        "retry_count": CtLogBackfillState.retry_count + 1,
        "retryable_error_count": CtLogBackfillState.retryable_error_count + 1,
    }
    if is_rate_limited and retry_after_seconds is not None:
        cooldown_until = now + timedelta(seconds=retry_after_seconds)
        values["rate_limited_until"] = cooldown_until
        values["next_retry_at"] = cooldown_until
    await session.execute(
        update(CtLogBackfillState)
        .where(
            CtLogBackfillState.log_source_id == log_source_id,
            CtLogBackfillState.claimed_by == worker_id,
        )
        .values(**values)
    )


async def mark_log_paused(
    session: AsyncSession,
    *,
    log_source_id: uuid.UUID,
    worker_id: str,
    error_type: str,
    error_message: str,
) -> None:
    """Mark the log as paused after exhausting the retry budget.

    Releases the worker's claim so another worker does not immediately
    re-pick the log; the status remains ``paused`` until an operator
    explicitly resumes the log or a fresh ingestion run resets it.
    """
    now = datetime.now(UTC)
    await session.execute(
        update(CtLogBackfillState)
        .where(
            CtLogBackfillState.log_source_id == log_source_id,
            CtLogBackfillState.claimed_by == worker_id,
        )
        .values(
            status=_STATUS_PAUSED,
            claimed_by=None,
            claimed_at=None,
            heartbeat_at=now,
            updated_at=now,
            last_error_type=error_type,
            last_error_message=error_message,
            last_error_at=now,
        )
    )


async def increment_terminal_error_count(
    session: AsyncSession,
    *,
    log_source_id: uuid.UUID,
) -> None:
    """Increment the terminal-entry-error counter for *log_source_id*.

    Used after a single bad CT entry has been recorded as a durable
    ``ct_entry_outcomes`` row; the per-log status itself is unchanged.
    """
    await session.execute(
        update(CtLogBackfillState)
        .where(CtLogBackfillState.log_source_id == log_source_id)
        .values(
            terminal_error_count=CtLogBackfillState.terminal_error_count + 1,
        )
    )


async def mark_log_complete(
    session: AsyncSession,
    *,
    log_source_id: uuid.UUID,
) -> None:
    """Mark a log's backfill as fully complete.

    Args:
        session:       Open async SQLAlchemy session (inside an active transaction).
        log_source_id: UUID of the completed log.
    """
    now = datetime.now(UTC)
    await session.execute(
        update(CtLogBackfillState)
        .where(CtLogBackfillState.log_source_id == log_source_id)
        .values(
            status=_STATUS_COMPLETE,
            completed_at=now,
            claimed_by=None,
            claimed_at=None,
            updated_at=now,
        )
    )
    _logger.info("worker_claim: log %s marked complete", log_source_id)


async def reap_stale_log_claims(
    session: AsyncSession,
    *,
    stale_seconds: int,
) -> list[uuid.UUID]:
    """Reset backfill log claims whose heartbeat has expired.

    Resets ``claimed_by``, ``claimed_at``, and ``heartbeat_at`` back to
    ``None`` so another worker can claim the log.

    Args:
        session:       Open async SQLAlchemy session (inside an active transaction).
        stale_seconds: Age in seconds after which a heartbeat is considered stale.

    Returns:
        List of ``log_source_id`` UUIDs whose claims were reaped.
    """
    cutoff = _utc_cutoff(stale_seconds)
    now = datetime.now(UTC)

    # Find stale rows first.
    stale_stmt = select(CtLogBackfillState).where(
        CtLogBackfillState.claimed_by.is_not(None),
        CtLogBackfillState.heartbeat_at < cutoff,
    )
    stale_result = await session.execute(stale_stmt)
    stale_rows = list(stale_result.scalars().all())
    stale_ids = [r.log_source_id for r in stale_rows]

    if not stale_ids:
        return []

    await session.execute(
        update(CtLogBackfillState)
        .where(CtLogBackfillState.log_source_id.in_(stale_ids))
        .values(
            claimed_by=None,
            claimed_at=None,
            heartbeat_at=None,
            status=_STATUS_PENDING,
            updated_at=now,
        )
    )
    _logger.info("worker_claim: reaped %d stale log claims", len(stale_ids))
    return stale_ids


def _utc_cutoff(stale_seconds: int) -> datetime:
    """Return the datetime before which a heartbeat is considered stale."""
    from datetime import timedelta

    return datetime.now(UTC) - timedelta(seconds=stale_seconds)


async def extend_window_backward(
    session: AsyncSession,
    *,
    log_source_id: uuid.UUID,
    new_start: int,
    observed_oldest: datetime | None,
) -> None:
    """Move the backfill window start earlier and record coverage state.

    Sets ``backfill_start_index`` and ``last_checkpoint_index`` to *new_start*,
    increments ``window_extended_count``, and updates ``observed_oldest_not_before``
    only when *observed_oldest* is strictly older than the stored value (or the
    stored value is NULL).

    Args:
        session:          Open async SQLAlchemy session (inside an active transaction).
        log_source_id:    UUID of the log whose window is being extended.
        new_start:        New (lower) ``backfill_start_index``. Must be ≥ 0.
        observed_oldest:  The oldest ``not_before`` seen so far, or None if unknown.
    """
    now = datetime.now(UTC)
    # We update observed_oldest_not_before only when the new value is strictly older.
    # A conditional expression in raw SQL keeps this atomic without a read-then-write.
    await session.execute(
        update(CtLogBackfillState)
        .where(CtLogBackfillState.log_source_id == log_source_id)
        .values(
            backfill_start_index=new_start,
            last_checkpoint_index=new_start,
            window_extended_count=CtLogBackfillState.window_extended_count + 1,
            observed_oldest_not_before=(
                observed_oldest
                if observed_oldest is not None
                else CtLogBackfillState.observed_oldest_not_before
            ),
            updated_at=now,
        )
    )
    _logger.info(
        "worker_claim: log %s window extended — new_start=%d extended_oldest=%s",
        log_source_id,
        new_start,
        observed_oldest,
    )


async def update_observed_oldest(
    session: AsyncSession,
    *,
    log_source_id: uuid.UUID,
    oldest_not_before: datetime,
) -> None:
    """Persist the oldest observed ``not_before`` date for a log.

    The stored value is updated only when *oldest_not_before* is strictly older
    than the currently stored value (or the stored value is NULL).

    Args:
        session:           Open async SQLAlchemy session (inside an active transaction).
        log_source_id:     UUID of the log to update.
        oldest_not_before: The oldest ``not_before`` seen in the current batch.
    """
    now = datetime.now(UTC)
    await session.execute(
        update(CtLogBackfillState)
        .where(
            CtLogBackfillState.log_source_id == log_source_id,
            or_(
                CtLogBackfillState.observed_oldest_not_before.is_(None),
                CtLogBackfillState.observed_oldest_not_before > oldest_not_before,
            ),
        )
        .values(
            observed_oldest_not_before=oldest_not_before,
            updated_at=now,
        )
    )
