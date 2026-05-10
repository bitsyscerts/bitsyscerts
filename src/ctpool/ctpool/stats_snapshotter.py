"""Stats snapshot loop: periodically computes and persists a full stats payload.

Responsibilities:
    - ``take_snapshot_once`` — runs all stats queries once, assembles the
      payload, and inserts a snapshot row.
    - ``run_snapshot_loop`` — runs ``take_snapshot_once`` on a configured
      interval and prunes old snapshot rows after each cycle.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from ctpool.backfill_state_queries import query_backfill_state_summary
from ctpool.config import Settings
from ctpool.db import create_engine, create_session_factory
from ctpool.db_contention_observability import read_db_contention_operator_snapshot
from ctpool.stats_assembler import assemble_stats_payload
from ctpool.stats_queries import (
    query_active_instance_settings,
    query_backfill_planned_counts,
    query_backfill_range_status_counts,
    query_database_size_bytes,
    query_db_storage,
    query_entry_outcome_counts,
    query_global_counts,
    query_ingestion_metrics_summary,
    query_ingestion_rate_windows,
    query_log_stats,
    query_tail_freshness,
)
from ctpool.stats_snapshot_repository import StatsSnapshotRepository
from ctpool.worker_queries import query_worker_summary

_logger = logging.getLogger(__name__)

_INGESTION_RATE_WINDOWS = [300, 3600]
_TAIL_STALE_THRESHOLD_SECONDS = 300
_SNAPSHOT_TYPE = "full"


async def take_snapshot_once(settings: Settings) -> dict[str, Any]:
    """Run all stats queries and persist one snapshot row.

    Args:
        settings: Active application settings.

    Returns:
        The assembled stats payload dict.
    """
    engine = create_engine(settings)
    factory = create_session_factory(engine)
    repo = StatsSnapshotRepository()

    t0 = time.monotonic()
    try:
        async with factory() as session:
            global_counts = await query_global_counts(session)
            database_size_bytes = await query_database_size_bytes(session)
            backfill_progress = await query_backfill_planned_counts(session)
            claim_timeout = settings.ct_backfill_claim_timeout_seconds
            backfill_status = await query_backfill_range_status_counts(
                session, claim_timeout
            )
            storage_data = await query_db_storage(session)
            contention = await read_db_contention_operator_snapshot(session, settings)
            rate_rows = await query_ingestion_rate_windows(
                session, _INGESTION_RATE_WINDOWS
            )
            freshness_row = await query_tail_freshness(
                session, _TAIL_STALE_THRESHOLD_SECONDS
            )
            outcome_counts = await query_entry_outcome_counts(session)
            metrics_summary = await query_ingestion_metrics_summary(session)
            audit_counts = await _query_audit_counts(session)
            per_log_rows = await query_log_stats(session)
            active_settings = await query_active_instance_settings(session)
            worker_summary = await query_worker_summary(
                session, stale_seconds=settings.ct_worker_stale_seconds
            )
            backfill_state = await query_backfill_state_summary(
                session, stale_seconds=settings.ct_worker_stale_seconds
            )
            from ctpool.maintenance_queries import query_latest_maintenance_run

            maintenance_run = await query_latest_maintenance_run(session)

        payload = assemble_stats_payload(
            global_counts=global_counts,
            database_size_bytes=database_size_bytes,
            backfill_progress=backfill_progress,
            backfill_status_counts=backfill_status,
            storage_data=storage_data,
            contention_snapshot=contention,
            rate_rows=rate_rows,
            freshness_row=freshness_row,
            outcome_counts=outcome_counts,
            metrics_summary=metrics_summary,
            audit_counts=audit_counts,
            per_log_rows=per_log_rows,
            active_settings=active_settings,
            worker_summary=worker_summary,
            backfill_state=backfill_state,
            maintenance_run=maintenance_run,
            maintenance_interval_seconds=settings.ct_maintenance_interval_seconds,
            dispatch_mode=settings.ct_backfill_dispatch_mode,
        )

        duration_ms = int((time.monotonic() - t0) * 1000)

        async with factory() as session:
            async with session.begin():
                await repo.insert_snapshot(
                    session,
                    snapshot_type=_SNAPSHOT_TYPE,
                    payload=_serialise_payload(payload),
                    duration_ms=duration_ms,
                )
                await repo.prune_old_snapshots(
                    session,
                    retention_hours=settings.ct_stats_snapshot_retention_hours,
                    snapshot_type=_SNAPSHOT_TYPE,
                )

        _logger.info(
            "Stats snapshot taken in %d ms (type=%s)",
            duration_ms,
            _SNAPSHOT_TYPE,
        )
        return payload

    finally:
        await engine.dispose()


async def run_snapshot_loop(settings: Settings) -> None:
    """Continuously take stats snapshots at the configured interval.

    Runs indefinitely.  Each cycle takes a snapshot then sleeps for
    ``ct_stats_heavy_refresh_seconds``.  Errors are logged and the loop
    continues.

    Args:
        settings: Active application settings.
    """
    interval = settings.ct_stats_heavy_refresh_seconds
    _logger.info(
        "Stats snapshot loop starting (interval=%d s, type=%s)",
        interval,
        _SNAPSHOT_TYPE,
    )
    while True:
        try:
            await take_snapshot_once(settings)
        except Exception:
            _logger.exception("Stats snapshot failed; will retry after interval")
        await asyncio.sleep(interval)


def _serialise_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Convert non-JSON-serialisable values to strings for JSONB storage.

    Converts :class:`~datetime.datetime` objects to ISO-8601 strings and
    :class:`uuid.UUID` objects to their string representation.
    """
    import json
    import uuid
    from datetime import datetime

    def _default(obj: Any) -> Any:
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, uuid.UUID):
            return str(obj)
        raise TypeError(f"Object of type {type(obj)} is not JSON serialisable")

    return json.loads(json.dumps(payload, default=_default))


async def _query_audit_counts(session: Any) -> dict[str, int]:
    """Return per-severity open audit finding counts.

    Isolated helper so the snapshotter does not need to import the
    certsapi audit constants directly.
    """
    from sqlalchemy import func, select

    from ctpool.models.audit_finding import CtAuditFinding

    stmt = (
        select(CtAuditFinding.severity, func.count().label("cnt"))
        .where(CtAuditFinding.status == "open")
        .group_by(CtAuditFinding.severity)
    )
    result = await session.execute(stmt)
    return {row.severity: int(row.cnt) for row in result}
