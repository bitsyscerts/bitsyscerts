"""Worker activity queries for the stats pipeline.

Exports:
    query_worker_summary — Produce a worker-summary dict for the stats assembler.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ctpool.models.log_backfill_state import CtLogBackfillState
from ctpool.models.log_source import CtLogSource
from ctpool.models.log_tail_cursor import CtLogTailCursor
from ctpool.models.worker_runtime import CtWorkerRuntime

_logger = logging.getLogger(__name__)

_STATUS_STOPPED = "stopped"
_SAFE_WORKER_ERROR_MESSAGES: dict[str, str] = {
    "RateLimitError": "Upstream rate limit",
    "FetchError": "Upstream fetch failure",
    "DatabaseError": "Database write failure",
    "ConfigurationError": "Configuration error",
    "DispatcherError": "Log dispatch failure",
    "ParseError": "Entry parse failure",
    "UnsupportedEntryTypeError": "Unsupported CT entry type",
}


def _coerce_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, int | float):
        return float(value)
    return None


def _coerce_int(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, int | float):
        return int(value)
    return None


def _coerce_iso(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, str):
        return value
    return None


def _detail_value(details: dict[str, Any], key: str) -> Any:
    value = details.get(key)
    return value if value is not None else None


def _first_non_none(*values: Any) -> Any:
    for value in values:
        if value is not None:
            return value
    return None


def _sanitize_worker_error_message(
    error_type: str | None,
    error_message: str | None,
) -> str | None:
    if error_type is None or error_message is None:
        return None
    return _SAFE_WORKER_ERROR_MESSAGES.get(error_type)


async def _query_backfill_claims(
    session: AsyncSession,
) -> dict[str, dict[str, Any]]:
    stmt = (
        select(CtLogBackfillState, CtLogSource)
        .join(CtLogSource, CtLogSource.id == CtLogBackfillState.log_source_id)
        .where(CtLogBackfillState.claimed_by.is_not(None))
    )
    result = await session.execute(stmt)

    claims: dict[str, dict[str, Any]] = {}
    for state, log in result.all():
        if state.claimed_by is None:
            continue
        claims[state.claimed_by] = {
            "log_source_id": str(state.log_source_id),
            "log_name": log.description,
            "log_url": log.url,
            "log_operator": log.operator_name,
            "checkpoint_index": state.last_checkpoint_index,
            "batch_start_index": state.backfill_start_index,
            "batch_end_index": state.backfill_end_index,
            "retry_count": int(state.retry_count or 0),
            "next_retry_at": _coerce_iso(state.next_retry_at),
            "rate_limited_until": _coerce_iso(state.rate_limited_until),
            "last_error_type": state.last_error_type,
            "last_error_message": state.last_error_message,
        }
    return claims


async def _query_tail_cursor_indexes(
    session: AsyncSession,
) -> dict[uuid.UUID, int]:
    result = await session.execute(select(CtLogTailCursor))
    return {row.log_source_id: row.next_index for row in result.scalars().all()}


async def _query_log_sources(
    session: AsyncSession,
    log_source_ids: set[uuid.UUID],
) -> dict[uuid.UUID, dict[str, str | None]]:
    if not log_source_ids:
        return {}

    stmt = select(CtLogSource).where(CtLogSource.id.in_(log_source_ids))
    result = await session.execute(stmt)
    return {
        row.id: {
            "log_name": row.description,
            "log_url": row.url,
            "log_operator": row.operator_name,
        }
        for row in result.scalars().all()
    }


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
        ``backfill_active``, ``stats_active``, ``maintenance_active``,
        ``unknown_active``, and ``items`` (list of per-worker dicts).
    """
    stmt = (
        select(CtWorkerRuntime)
        .where(CtWorkerRuntime.status != _STATUS_STOPPED)
        .order_by(CtWorkerRuntime.started_at.desc())
    )
    result = await session.execute(stmt)
    rows = list(result.scalars().all())
    backfill_claims = await _query_backfill_claims(session)
    tail_indexes = await _query_tail_cursor_indexes(session)
    log_sources = await _query_log_sources(
        session,
        {row.log_source_id for row in rows if row.log_source_id is not None},
    )

    now = datetime.now(UTC)
    cutoff = now - timedelta(seconds=stale_seconds)

    items: list[dict[str, Any]] = []
    active_total = 0
    stale_total = 0
    tail_active = 0
    backfill_active = 0
    stats_active = 0
    maintenance_active = 0
    unknown_active = 0

    for row in rows:
        details = row.details_json if isinstance(row.details_json, dict) else {}
        backfill_claim = backfill_claims.get(row.worker_id, {})
        runtime_log = (
            log_sources.get(row.log_source_id)
            if row.log_source_id is not None
            else None
        )
        is_stale = row.last_heartbeat_at < cutoff
        age_seconds = int((now - row.last_heartbeat_at).total_seconds())
        last_error_type = _first_non_none(
            row.last_error_type,
            backfill_claim.get("last_error_type"),
        )
        last_error_message = _sanitize_worker_error_message(
            last_error_type,
            _first_non_none(
                row.last_error_message,
                backfill_claim.get("last_error_message"),
            ),
        )

        if is_stale:
            stale_total += 1
        else:
            active_total += 1
            if row.worker_kind == "tail":
                tail_active += 1
            elif row.worker_kind == "backfill":
                backfill_active += 1
            elif row.worker_kind == "stats-snapshotter":
                stats_active += 1
            elif row.worker_kind == "maintenance":
                maintenance_active += 1
            else:
                unknown_active += 1

        current_index = row.current_index
        if current_index is None and row.log_source_id is not None:
            current_index = tail_indexes.get(row.log_source_id)

        items.append(
            {
                "worker_id": row.worker_id,
                "worker_kind": row.worker_kind,
                "log_source_id": (
                    str(row.log_source_id)
                    if row.log_source_id is not None
                    else backfill_claim.get("log_source_id")
                ),
                "log_name": _first_non_none(
                    row.log_name,
                    runtime_log.get("log_name") if runtime_log is not None else None,
                    backfill_claim.get("log_name"),
                ),
                "log_url": _first_non_none(
                    runtime_log.get("log_url") if runtime_log is not None else None,
                    backfill_claim.get("log_url"),
                ),
                "log_operator": _first_non_none(
                    (
                        runtime_log.get("log_operator")
                        if runtime_log is not None
                        else None
                    ),
                    backfill_claim.get("log_operator"),
                ),
                "direction": row.direction,
                "status": row.status,
                "is_stale": is_stale,
                "last_heartbeat_at": row.last_heartbeat_at.isoformat(),
                "last_heartbeat_age_seconds": age_seconds,
                "started_at": row.started_at.isoformat(),
                "current_index": current_index,
                "checkpoint_index": _first_non_none(
                    _coerce_int(_detail_value(details, "checkpoint_index")),
                    row.last_successful_index,
                    backfill_claim.get("checkpoint_index"),
                ),
                "batch_start_index": row.batch_start_index
                if row.batch_start_index is not None
                else backfill_claim.get("batch_start_index"),
                "batch_end_index": row.batch_end_index
                if row.batch_end_index is not None
                else backfill_claim.get("batch_end_index"),
                "processed_entries": row.processed_entries,
                "stored_certificates": row.stored_certificates,
                "duplicate_certificates": row.duplicate_certificates,
                "observed_hostnames": row.observed_hostnames,
                "new_hostnames": row.new_hostnames,
                "parse_errors": row.parse_errors,
                "retryable_errors": row.retryable_errors,
                "terminal_errors": row.terminal_errors,
                "observations_per_min": _coerce_float(
                    _detail_value(details, "observations_per_min")
                ),
                "new_unique_certificates_per_min": _coerce_float(
                    _detail_value(details, "new_unique_certificates_per_min")
                ),
                "duplicate_certificates_per_min": _coerce_float(
                    _detail_value(details, "duplicate_certificates_per_min")
                ),
                "new_unique_hostnames_per_min": _coerce_float(
                    _detail_value(details, "new_unique_hostnames_per_min")
                ),
                "known_hostnames_per_min": _coerce_float(
                    _detail_value(details, "known_hostnames_per_min")
                ),
                "retry_count": _first_non_none(
                    _coerce_int(_detail_value(details, "retry_count")),
                    backfill_claim.get("retry_count"),
                ),
                "next_retry_at": _first_non_none(
                    _coerce_iso(_detail_value(details, "next_retry_at")),
                    backfill_claim.get("next_retry_at"),
                ),
                "rate_limited_until": _first_non_none(
                    _coerce_iso(_detail_value(details, "rate_limited_until")),
                    backfill_claim.get("rate_limited_until"),
                ),
                "last_error_type": last_error_type,
                "last_error_message": last_error_message,
            }
        )

    return {
        "active_total": active_total,
        "stale_total": stale_total,
        "tail_active": tail_active,
        "backfill_active": backfill_active,
        "stats_active": stats_active,
        "maintenance_active": maintenance_active,
        "unknown_active": unknown_active,
        "items": items,
    }
