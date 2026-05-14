"""Per-log backfill state queries for the stats pipeline.

Exports:
    query_backfill_state_summary — Snapshot of per-log backfill state.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ctpool.models.log_backfill_state import CtLogBackfillState
from ctpool.models.log_source import CtLogSource

_logger = logging.getLogger(__name__)


def _progress_percent(
    start: int | None,
    end: int | None,
    checkpoint: int | None,
) -> float | None:
    """Compute backfill progress as a percentage in ``[0, 100]``.

    Returns ``None`` when the window or checkpoint is not yet known.
    """
    if start is None or end is None or checkpoint is None:
        return None
    span = max(0, end - start)
    if span == 0:
        return 100.0
    done = max(0, min(checkpoint - start, span))
    return round((done / span) * 100.0, 2)


async def query_backfill_state_summary(
    session: AsyncSession,
    *,
    stale_seconds: int,
) -> dict[str, Any]:
    """Return per-log backfill state for the stats payload.

    Args:
        session:       Open async SQLAlchemy session.
        stale_seconds: Heartbeat age beyond which a claim is considered stale.

    Returns:
        Dict with status counters and a per-log ``items`` list.
    """
    stmt = (
        select(CtLogBackfillState, CtLogSource)
        .join(CtLogSource, CtLogSource.id == CtLogBackfillState.log_source_id)
        .order_by(CtLogSource.description.asc())
    )
    result = await session.execute(stmt)

    now = datetime.now(UTC)
    cutoff = now - timedelta(seconds=stale_seconds)

    items: list[dict[str, Any]] = []
    counters = {
        "total_logs": 0,
        "pending": 0,
        "claimed": 0,
        "processing": 0,
        "retrying": 0,
        "rate_limited": 0,
        "degraded": 0,
        "paused": 0,
        "complete": 0,
        "error": 0,
        "stale": 0,
    }

    for state, log in result.all():
        counters["total_logs"] += 1
        bucket = state.status if state.status in counters else "pending"
        counters[bucket] += 1

        is_stale = (
            state.claimed_by is not None
            and state.heartbeat_at is not None
            and state.heartbeat_at < cutoff
        )
        if is_stale:
            counters["stale"] += 1

        heartbeat_age: float | None = None
        if state.heartbeat_at is not None:
            heartbeat_age = round((now - state.heartbeat_at).total_seconds(), 2)

        items.append(
            {
                "log_source_id": str(state.log_source_id),
                "log_name": log.description,
                "log_url": log.url,
                "status": state.status,
                "claimed_by": state.claimed_by,
                "is_stale": is_stale,
                "checkpoint_index": state.last_checkpoint_index,
                "backfill_start_index": state.backfill_start_index,
                "backfill_end_index": state.backfill_end_index,
                "progress_percent": _progress_percent(
                    state.backfill_start_index,
                    state.backfill_end_index,
                    state.last_checkpoint_index,
                ),
                "last_heartbeat_age_seconds": heartbeat_age,
                "last_error_type": state.last_error_type,
                "last_error_message": state.last_error_message,
                "last_error_at": (
                    state.last_error_at.isoformat()
                    if state.last_error_at is not None
                    else None
                ),
                "next_retry_at": (
                    state.next_retry_at.isoformat()
                    if state.next_retry_at is not None
                    else None
                ),
                "rate_limited_until": (
                    state.rate_limited_until.isoformat()
                    if state.rate_limited_until is not None
                    else None
                ),
                "retry_count": int(state.retry_count or 0),
                "retryable_error_count": int(state.retryable_error_count or 0),
                "terminal_error_count": int(state.terminal_error_count or 0),
                "completed_at": (
                    state.completed_at.isoformat()
                    if state.completed_at is not None
                    else None
                ),
            }
        )

    return {**counters, "items": items}
