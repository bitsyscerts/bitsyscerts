"""Worker activity queries for the stats pipeline.

Exports:
    query_worker_summary — Produce a worker-summary dict for the stats assembler.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ctpool.models.worker_runtime import CtWorkerRuntime

_logger = logging.getLogger(__name__)

_STATUS_STOPPED = "stopped"


async def query_worker_summary(
    session: AsyncSession,
    *,
    stale_seconds: int,
) -> dict[str, Any]:
    """Query ct_worker_runtime and return a worker-summary dict.

    The returned dict matches the ``worker_summary`` key expected by
    :func:`~ctpool.stats_assembler.assemble_stats_payload`.

    Args:
        session:       Open async SQLAlchemy session.
        stale_seconds: Seconds without heartbeat that classifies a worker as stale.

    Returns:
        Dict with keys: ``active_total``, ``stale_total``, ``tail_active``,
        ``backfill_active``, and ``items`` (list of per-worker dicts).
    """
    stmt = (
        select(CtWorkerRuntime)
        .where(CtWorkerRuntime.status != _STATUS_STOPPED)
        .order_by(CtWorkerRuntime.started_at.desc())
    )
    result = await session.execute(stmt)
    rows = list(result.scalars().all())

    now = datetime.now(UTC)
    cutoff = now - timedelta(seconds=stale_seconds)

    items: list[dict[str, Any]] = []
    active_total = 0
    stale_total = 0
    tail_active = 0
    backfill_active = 0

    for row in rows:
        is_stale = row.last_heartbeat_at < cutoff
        age_seconds = int((now - row.last_heartbeat_at).total_seconds())

        if is_stale:
            stale_total += 1
        else:
            active_total += 1
            if row.worker_kind == "tail":
                tail_active += 1
            elif row.worker_kind == "backfill":
                backfill_active += 1

        items.append(
            {
                "worker_id": row.worker_id,
                "worker_kind": row.worker_kind,
                "log_source_id": str(row.log_source_id) if row.log_source_id else None,
                "log_name": row.log_name,
                "direction": row.direction,
                "status": row.status,
                "is_stale": is_stale,
                "last_heartbeat_at": row.last_heartbeat_at.isoformat(),
                "last_heartbeat_age_seconds": age_seconds,
                "started_at": row.started_at.isoformat(),
                "current_index": row.current_index,
                "processed_entries": row.processed_entries,
                "stored_certificates": row.stored_certificates,
                "duplicate_certificates": row.duplicate_certificates,
                "observed_hostnames": row.observed_hostnames,
                "new_hostnames": row.new_hostnames,
                "parse_errors": row.parse_errors,
                "retryable_errors": row.retryable_errors,
                "terminal_errors": row.terminal_errors,
                "last_error_type": row.last_error_type,
                "last_error_message": row.last_error_message,
            }
        )

    return {
        "active_total": active_total,
        "stale_total": stale_total,
        "tail_active": tail_active,
        "backfill_active": backfill_active,
        "items": items,
    }
