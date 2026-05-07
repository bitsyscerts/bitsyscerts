"""Pure async SQL query functions that return raw rows for audit gap detection.

Each function queries a single type of gap and returns a sequence of
RowMapping dicts. No ORM models are constructed here — that is the
responsibility of audit_checker.

Exports:
    query_stale_backfill_claims        — Ranges stuck in in_progress past timeout.
    query_failed_backfill_ranges       — Ranges with status=failed.
    query_missing_entry_outcomes       — Completed ranges with index gaps in outcomes.
    query_missing_observations_without_outcome — Observations lacking outcome rows.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import text
from sqlalchemy.engine import RowMapping
from sqlalchemy.ext.asyncio import AsyncSession


async def query_stale_backfill_claims(
    session: AsyncSession,
    claim_timeout_seconds: int,
) -> list[RowMapping]:
    """Return in_progress ranges whose heartbeat has not been refreshed recently.

    Args:
        session:               Active async database session.
        claim_timeout_seconds: Seconds after which a silent in_progress range
                               is considered stale.
    """
    cutoff = datetime.now(UTC) - timedelta(seconds=claim_timeout_seconds)
    result = await session.execute(
        text(
            """
            SELECT id, log_source_id, start_index, end_index, claimed_by,
                   claimed_at, heartbeat_at
            FROM ct_log_backfill_ranges
            WHERE status = 'in_progress'
              AND COALESCE(heartbeat_at, claimed_at) < :cutoff
            ORDER BY COALESCE(heartbeat_at, claimed_at) ASC
            LIMIT 500
            """
        ),
        {"cutoff": cutoff},
    )
    return list(result.mappings())


async def query_failed_backfill_ranges(
    session: AsyncSession,
) -> list[RowMapping]:
    """Return all ranges with status=failed that have not been repaired yet.

    Excludes repair ranges that already have an associated audit finding in a
    terminal state (resolved/ignored/failed) to avoid re-reporting.
    """
    result = await session.execute(
        text(
            """
            SELECT r.id, r.log_source_id, r.start_index, r.end_index,
                   r.last_error, r.attempt_count, r.range_kind
            FROM ct_log_backfill_ranges r
            WHERE r.status = 'failed'
            ORDER BY r.created_at ASC
            LIMIT 500
            """
        ),
    )
    return list(result.mappings())


async def query_missing_entry_outcomes(
    session: AsyncSession,
) -> list[RowMapping]:
    """Find completed backfill ranges that are missing outcome rows.

    Returns one row per (log_source_id, start_index, end_index) span where
    the count of outcome rows is less than (end_index - start_index + 1).
    """
    result = await session.execute(
        text(
            """
            SELECT r.id AS range_id,
                   r.log_source_id,
                   r.start_index,
                   r.end_index,
                   (r.end_index - r.start_index + 1) AS expected_count,
                   COUNT(o.id)::bigint AS actual_count,
                   (r.end_index - r.start_index + 1 - COUNT(o.id))::int
                       AS missing_count
            FROM ct_log_backfill_ranges r
            LEFT JOIN ct_entry_outcomes o
                   ON o.log_source_id = r.log_source_id
                  AND o.log_index BETWEEN r.start_index AND r.end_index
            WHERE r.status = 'complete'
            GROUP BY r.id, r.log_source_id, r.start_index, r.end_index
            HAVING COUNT(o.id) < (r.end_index - r.start_index + 1)
            ORDER BY missing_count DESC
            LIMIT 500
            """
        ),
    )
    return list(result.mappings())


async def query_missing_observations_without_outcome(
    session: AsyncSession,
) -> list[RowMapping]:
    """Find ct_log_observations rows that have no corresponding outcome row.

    Returns up to 500 distinct (log_source_id, log_index) pairs where an
    observation was recorded but no outcome row exists.
    """
    result = await session.execute(
        text(
            """
            SELECT obs.id AS observation_id,
                   obs.log_source_id,
                   obs.log_index
            FROM ct_log_observations obs
            WHERE NOT EXISTS (
                SELECT 1
                FROM ct_entry_outcomes o
                WHERE o.log_source_id = obs.log_source_id
                  AND o.log_index = obs.log_index
            )
            ORDER BY obs.log_source_id, obs.log_index
            LIMIT 500
            """
        ),
    )
    return list(result.mappings())
