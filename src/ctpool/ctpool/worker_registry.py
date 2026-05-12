"""Worker registration, heartbeat, and stale-detection for ct_worker_runtime.

Exports:
    register_worker     — Insert or refresh a worker row on startup.
    heartbeat_worker    — Update heartbeat, status, and counters for a running worker.
    mark_worker_stopped — Record graceful shutdown for a worker.
    list_active_workers — Return all non-stopped worker rows.
    list_stale_workers  — Return workers whose heartbeat has expired.
    WorkerCounters      — Typed counters struct for heartbeat updates.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ctpool.models.worker_runtime import CtWorkerRuntime

_logger = logging.getLogger(__name__)

_STATUS_STARTING = "starting"
_STATUS_STOPPED = "stopped"
_UNSET = object()


@dataclass
class WorkerCounters:
    """Ingestion counters carried in each heartbeat update."""

    processed_entries: int = 0
    stored_certificates: int = 0
    duplicate_certificates: int = 0
    observed_hostnames: int = 0
    new_hostnames: int = 0
    parse_errors: int = 0
    retryable_errors: int = 0
    terminal_errors: int = 0
    last_error_type: str | None = None
    last_error_message: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


async def register_worker(
    session: AsyncSession,
    *,
    worker_id: str,
    worker_kind: str,
) -> CtWorkerRuntime:
    """Insert a new worker row in ``ct_worker_runtime``.

    Returns the created ORM instance (not yet flushed to the connection —
    caller must be inside a transaction that will commit).

    Args:
        session:     Open async SQLAlchemy session (inside an active transaction).
        worker_id:   Stable process identity string (e.g. ``hostname:PID``).
        worker_kind: Worker runtime category (e.g. ``tail`` or ``backfill``).

    Returns:
        The newly created :class:`CtWorkerRuntime` instance.
    """
    now = datetime.now(UTC)
    row = CtWorkerRuntime(
        id=uuid.uuid4(),
        worker_id=worker_id,
        worker_kind=worker_kind,
        status=_STATUS_STARTING,
        last_heartbeat_at=now,
        started_at=now,
        updated_at=now,
    )
    session.add(row)
    _logger.info("worker registered worker_id=%s kind=%s", worker_id, worker_kind)
    return row


async def heartbeat_worker(
    session: AsyncSession,
    *,
    row_id: uuid.UUID,
    status: str,
    current_index: int | None | object = _UNSET,
    last_successful_index: int | None | object = _UNSET,
    batch_start_index: int | None | object = _UNSET,
    batch_end_index: int | None | object = _UNSET,
    log_source_id: uuid.UUID | None | object = _UNSET,
    log_name: str | None | object = _UNSET,
    direction: str | None | object = _UNSET,
    details_json: dict[str, Any] | None | object = _UNSET,
    counters: WorkerCounters | None = None,
) -> None:
    """Refresh ``last_heartbeat_at`` and runtime state for a worker row.

    Writes are accumulated in the session; caller must commit.

    Args:
        session:           Open async SQLAlchemy session inside an active transaction.
        row_id:            Primary key of the :class:`CtWorkerRuntime` row.
        status:            Current worker status string.
        current_index:     Most recent log index being processed; pass
                   ``None`` to clear.
        last_successful_index: Durable checkpoint or last successful index.
        batch_start_index: Start of the current batch range; pass ``None`` to clear.
        batch_end_index:   End of the current batch range; pass ``None`` to clear.
        log_source_id:     Assigned log UUID when the worker is working a specific log.
        log_name:          Assigned log description for operator display.
        direction:         Optional direction or role label for operator display.
        details_json:      Optional normalized details payload; pass ``None`` to clear.
        counters:          Cumulative ingestion counters since the last heartbeat.
    """
    now = datetime.now(UTC)
    values: dict[str, Any] = {
        "last_heartbeat_at": now,
        "updated_at": now,
        "status": status,
    }
    if current_index is not _UNSET:
        values["current_index"] = current_index
    if last_successful_index is not _UNSET:
        values["last_successful_index"] = last_successful_index
    if batch_start_index is not _UNSET:
        values["batch_start_index"] = batch_start_index
    if batch_end_index is not _UNSET:
        values["batch_end_index"] = batch_end_index
    if log_source_id is not _UNSET:
        values["log_source_id"] = log_source_id
    if log_name is not _UNSET:
        values["log_name"] = log_name
    if direction is not _UNSET:
        values["direction"] = direction
    if counters is not None:
        values.update(
            {
                "processed_entries": counters.processed_entries,
                "stored_certificates": counters.stored_certificates,
                "duplicate_certificates": counters.duplicate_certificates,
                "observed_hostnames": counters.observed_hostnames,
                "new_hostnames": counters.new_hostnames,
                "parse_errors": counters.parse_errors,
                "retryable_errors": counters.retryable_errors,
                "terminal_errors": counters.terminal_errors,
                "last_error_type": counters.last_error_type,
                "last_error_message": counters.last_error_message,
            }
        )
        if details_json is _UNSET and counters.extra:
            values["details_json"] = counters.extra
    if details_json is not _UNSET:
        values["details_json"] = details_json

    stmt = update(CtWorkerRuntime).where(CtWorkerRuntime.id == row_id).values(**values)
    await session.execute(stmt)


async def mark_worker_stopped(
    session: AsyncSession,
    *,
    row_id: uuid.UUID,
) -> None:
    """Record graceful shutdown for a worker.

    Sets ``status = 'stopped'`` and ``stopped_at = now()``.

    Args:
        session: Open async SQLAlchemy session inside an active transaction.
        row_id:  Primary key of the :class:`CtWorkerRuntime` row.
    """
    now = datetime.now(UTC)
    stmt = (
        update(CtWorkerRuntime)
        .where(CtWorkerRuntime.id == row_id)
        .values(status=_STATUS_STOPPED, stopped_at=now, updated_at=now)
    )
    await session.execute(stmt)
    _logger.info("worker marked stopped row_id=%s", row_id)


async def list_active_workers(
    session: AsyncSession,
) -> list[CtWorkerRuntime]:
    """Return all non-stopped worker rows ordered by started_at descending.

    Args:
        session: Open async SQLAlchemy session.

    Returns:
        List of :class:`CtWorkerRuntime` rows with ``status != 'stopped'``.
    """
    stmt = (
        select(CtWorkerRuntime)
        .where(CtWorkerRuntime.status != _STATUS_STOPPED)
        .order_by(CtWorkerRuntime.started_at.desc())
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def list_stale_workers(
    session: AsyncSession,
    *,
    stale_seconds: int,
) -> list[CtWorkerRuntime]:
    """Return non-stopped workers whose heartbeat has expired.

    A worker is stale when:
        ``last_heartbeat_at < now() - stale_seconds``
    and its status is not ``'stopped'``.

    Args:
        session:       Open async SQLAlchemy session.
        stale_seconds: Age in seconds after which a heartbeat is considered stale.

    Returns:
        List of stale :class:`CtWorkerRuntime` rows.
    """
    from sqlalchemy import text as sa_text

    cutoff_expr = sa_text("now() - make_interval(secs => :secs)").bindparams(
        secs=float(stale_seconds)
    )

    stmt = (
        select(CtWorkerRuntime)
        .where(
            CtWorkerRuntime.status != _STATUS_STOPPED,
            CtWorkerRuntime.last_heartbeat_at < cutoff_expr,
        )
        .order_by(CtWorkerRuntime.last_heartbeat_at.asc())
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())
