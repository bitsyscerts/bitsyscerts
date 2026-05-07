"""Raw async DB queries that feed the stats snapshot assembler.

Each function accepts an :class:`~sqlalchemy.ext.asyncio.AsyncSession` and
returns a plain Python value (dict, int, or list).  Keeping query logic here
makes the assembler and CLI testable without importing certsapi.

NOTE (201-500 line warning zone): This module consolidates all stats query
functions in one place to avoid fragmentation across many single-function
files.  Each function is independently unit-testable.  If more query concerns
are added, extract into per-domain query modules.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import case, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from ctpool.models.certificate import Certificate
from ctpool.models.certificate_hostname import CertificateHostname
from ctpool.models.entry_outcome import CtEntryOutcome
from ctpool.models.hostname import Hostname
from ctpool.models.ingestion_metric import IngestionMetric
from ctpool.models.log_backfill_range import CtLogBackfillRange
from ctpool.models.observation import CtLogObservation
from ctpool.outcome_constants import ALL_OUTCOMES

_logger = logging.getLogger(__name__)


async def query_global_counts(session: AsyncSession) -> dict[str, int]:
    """Return total hostname, certificate, observation, and cert-hostname counts.

    Args:
        session: Active async SQLAlchemy session.

    Returns:
        Dict with keys: hostnames, certificates, observations, cert_hostnames.
    """
    stmt = select(
        select(func.count()).select_from(Hostname).scalar_subquery().label("hostnames"),
        select(func.count())
        .select_from(Certificate)
        .scalar_subquery()
        .label("certificates"),
        select(func.count())
        .select_from(CtLogObservation)
        .scalar_subquery()
        .label("observations"),
        select(func.count())
        .select_from(CertificateHostname)
        .scalar_subquery()
        .label("cert_hostnames"),
    )
    result = await session.execute(stmt)
    row = result.one()
    return {
        "hostnames": int(row.hostnames),
        "certificates": int(row.certificates),
        "observations": int(row.observations),
        "cert_hostnames": int(row.cert_hostnames),
    }


async def query_database_size_bytes(session: AsyncSession) -> int:
    """Return the current PostgreSQL database size in bytes.

    Args:
        session: Active async SQLAlchemy session.

    Returns:
        Database size in bytes.
    """
    result = await session.execute(
        text("SELECT pg_database_size(current_database()) AS sz")
    )
    return int(result.scalar_one())


async def query_backfill_planned_counts(session: AsyncSession) -> dict[str, int]:
    """Return total and completed observation counts across all backfill ranges.

    Args:
        session: Active async SQLAlchemy session.

    Returns:
        Dict with keys: planned_total, planned_completed.
    """
    stmt = select(
        func.coalesce(
            func.sum(CtLogBackfillRange.end_index - CtLogBackfillRange.start_index),
            0,
        ).label("total"),
        func.coalesce(
            func.sum(
                case(
                    (
                        CtLogBackfillRange.status == "complete",
                        CtLogBackfillRange.end_index - CtLogBackfillRange.start_index,
                    ),
                    else_=0,
                )
            ),
            0,
        ).label("completed"),
    ).select_from(CtLogBackfillRange)
    result = await session.execute(stmt)
    row = result.one()
    return {
        "planned_total": int(row.total),
        "planned_completed": int(row.completed),
    }


async def query_backfill_range_status_counts(
    session: AsyncSession,
    claim_timeout_seconds: int,
) -> dict[str, int]:
    """Return backfill range status counts, separating stale in_progress ranges.

    Args:
        session: Active async SQLAlchemy session.
        claim_timeout_seconds: Age in seconds after which an in_progress range
            is classified as stale.

    Returns:
        Dict with keys: pending, in_progress, stale_in_progress, completed, failed.
    """
    cutoff = datetime.now(UTC) - timedelta(seconds=claim_timeout_seconds)
    stale_condition = (
        func.coalesce(CtLogBackfillRange.heartbeat_at, CtLogBackfillRange.claimed_at)
        < cutoff
    )
    stmt = select(
        func.count().filter(CtLogBackfillRange.status == "pending").label("pending"),
        func.count()
        .filter(CtLogBackfillRange.status == "in_progress", ~stale_condition)
        .label("in_progress"),
        func.count()
        .filter(CtLogBackfillRange.status == "in_progress", stale_condition)
        .label("stale_in_progress"),
        func.count().filter(CtLogBackfillRange.status == "complete").label("completed"),
        func.count().filter(CtLogBackfillRange.status == "failed").label("failed"),
    ).select_from(CtLogBackfillRange)
    result = await session.execute(stmt)
    row = result.one()
    return {
        "pending": int(row.pending),
        "in_progress": int(row.in_progress),
        "stale_in_progress": int(row.stale_in_progress),
        "completed": int(row.completed),
        "failed": int(row.failed),
    }


async def query_entry_outcome_counts(session: AsyncSession) -> dict[str, int]:
    """Return per-outcome row counts from ``ct_entry_outcomes``.

    Args:
        session: Active async SQLAlchemy session.

    Returns:
        Dict mapping outcome name to count; all known outcomes are present.
    """
    stmt = select(CtEntryOutcome.outcome, func.count().label("cnt")).group_by(
        CtEntryOutcome.outcome
    )
    result = await session.execute(stmt)
    counts: dict[str, int] = dict.fromkeys(ALL_OUTCOMES, 0)
    for row in result:
        counts[row.outcome] = int(row.cnt)
    return counts


async def query_ingestion_rate_windows(
    session: AsyncSession,
    windows_seconds: list[int],
) -> list[dict[str, Any]]:
    """Return ingestion throughput sums for each requested time window.

    Args:
        session: Active async SQLAlchemy session.
        windows_seconds: List of window durations in seconds.

    Returns:
        List of dicts with keys: window_seconds, entries_fetched, certs_upserted,
        hostnames_upserted.
    """
    rows = []
    for window_seconds in windows_seconds:
        cutoff = datetime.now(UTC) - timedelta(seconds=window_seconds)
        stmt = select(
            func.coalesce(func.sum(IngestionMetric.entries_fetched), 0).label(
                "entries_fetched"
            ),
            func.coalesce(func.sum(IngestionMetric.certs_upserted), 0).label(
                "certs_upserted"
            ),
            func.coalesce(func.sum(IngestionMetric.hostnames_upserted), 0).label(
                "hostnames_upserted"
            ),
        ).where(IngestionMetric.snapshot_at >= cutoff)
        result = (await session.execute(stmt)).mappings().one()
        rows.append({"window_seconds": window_seconds, **dict(result)})  # type: ignore[arg-type]
    return rows


async def query_tail_freshness(
    session: AsyncSession,
    stale_threshold_seconds: int,
) -> dict[str, Any]:
    """Return oldest lag, median lag, and stale count across all tail cursors.

    Cursors with ``updated_at IS NULL`` are counted as stale.

    Args:
        session: Active async SQLAlchemy session.
        stale_threshold_seconds: Lag threshold in seconds for classifying stale.

    Returns:
        Dict with keys: oldest_lag_seconds, median_lag_seconds, stale_log_count.
    """
    stmt = text("""
        SELECT
            MAX(
                EXTRACT(EPOCH FROM (now() - updated_at))
            )::int AS oldest_lag_seconds,
            PERCENTILE_CONT(0.5) WITHIN GROUP (
                ORDER BY EXTRACT(EPOCH FROM (now() - updated_at))
            )::int AS median_lag_seconds,
            COUNT(*) FILTER (
                WHERE updated_at IS NULL
                   OR EXTRACT(EPOCH FROM (now() - updated_at)) > :threshold
            ) AS stale_log_count
        FROM ct_log_tail_cursors
    """)
    result = await session.execute(stmt, {"threshold": stale_threshold_seconds})
    row = result.mappings().one()
    return dict(row)


async def query_ingestion_metrics_summary(
    session: AsyncSession,
) -> dict[str, Any]:
    """Return ingestion_metrics row count and oldest snapshot timestamp.

    Args:
        session: Active async SQLAlchemy session.

    Returns:
        Dict with keys: row_count, oldest_at.
    """
    stmt = select(
        func.count().label("row_count"),
        func.min(IngestionMetric.snapshot_at).label("oldest_at"),
    ).select_from(IngestionMetric)
    result = await session.execute(stmt)
    row = result.one()
    return {"row_count": int(row.row_count), "oldest_at": row.oldest_at}


async def query_log_stats(
    session: AsyncSession,
) -> list[dict[str, Any]]:
    """Return per-CT-log stats rows for active log sources.

    Args:
        session: Active async SQLAlchemy session.

    Returns:
        List of dicts compatible with the per-log stats assembler.
    """
    stmt = text("""
        SELECT
            ls.id,
            ls.description,
            ls.url,
            ls.log_state,
            lrs.tree_size       AS tail_position,
            ltc.updated_at      AS last_tail_sync,
            COUNT(lbr.id)       AS total_ranges,
            COUNT(lbr.id) FILTER (WHERE lbr.status = 'complete') AS complete_ranges
        FROM ct_log_sources ls
        LEFT JOIN ct_log_runtime_state lrs ON lrs.log_source_id = ls.id
        LEFT JOIN ct_log_tail_cursors ltc ON ltc.log_source_id = ls.id
        LEFT JOIN ct_log_backfill_ranges lbr ON lbr.log_source_id = ls.id
        GROUP BY ls.id, ls.description, ls.url, ls.log_state,
                 lrs.tree_size, ltc.updated_at
        ORDER BY ls.description
    """)
    result = await session.execute(stmt)
    return [dict(row) for row in result.mappings()]


async def query_db_storage(session: AsyncSession) -> dict[str, Any]:
    """Return total DB size and per-table storage from pg_* system functions.

    Args:
        session: Active async SQLAlchemy session.

    Returns:
        Dict with ``total`` (total_size_bytes, total_size_pretty) and
        ``tables`` (list of per-table rows).
    """
    total_stmt = text("""
        SELECT
            pg_database_size(current_database()) AS total_size_bytes,
            pg_size_pretty(
                pg_database_size(current_database())
            ) AS total_size_pretty
    """)
    total_row = dict((await session.execute(total_stmt)).mappings().one())
    table_stmt = text("""
        SELECT
            relname AS table_name,
            n_live_tup AS row_estimate,
            pg_total_relation_size(relid) AS size_bytes,
            pg_size_pretty(pg_total_relation_size(relid)) AS size_pretty
        FROM pg_stat_user_tables
        ORDER BY size_bytes DESC
    """)
    table_rows = [dict(r) for r in (await session.execute(table_stmt)).mappings().all()]
    return {"total": total_row, "tables": table_rows}


async def query_active_instance_settings(
    session: AsyncSession,
) -> Any:
    """Return the active CtInstanceSettings row, or None.

    Args:
        session: Active async SQLAlchemy session.

    Returns:
        :class:`~ctpool.models.instance_settings.CtInstanceSettings` or ``None``.
    """
    from ctpool.models.instance_settings import CtInstanceSettings

    stmt = select(CtInstanceSettings).limit(1)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()
