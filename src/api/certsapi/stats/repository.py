"""Ingestion statistics database queries.

# File consolidation rationale (lines 201-500 warning zone):
# All query methods here serve a single API endpoint (/v1/stats).  Splitting
# into multiple repository classes would require multiple injected dependencies
# in the service layer with no domain separation benefit.  Consolidation is
# justified until the stats endpoint grows a second distinct query domain.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from ctpool.audit_constants import (
    SEVERITY_CRITICAL,
    SEVERITY_ERROR,
    SEVERITY_INFO,
    SEVERITY_WARNING,
    STATUS_OPEN,
)
from ctpool.config import Settings as CtPoolSettings
from ctpool.db_contention_observability import read_db_contention_operator_snapshot
from ctpool.db_contention_types import DbContentionOperatorSnapshot
from ctpool.models.audit_finding import CtAuditFinding
from ctpool.models.certificate import Certificate
from ctpool.models.certificate_hostname import CertificateHostname
from ctpool.models.entry_outcome import CtEntryOutcome
from ctpool.models.hostname import Hostname
from ctpool.models.ingestion_metric import IngestionMetric
from ctpool.models.instance_settings import CtInstanceSettings
from ctpool.models.log_backfill_range import CtLogBackfillRange
from ctpool.models.log_source import CtLogSource
from ctpool.models.log_tail_cursor import CtLogTailCursor
from ctpool.models.observation import CtLogObservation
from ctpool.outcome_constants import ALL_OUTCOMES
from sqlalchemy import case, func, select, text
from sqlalchemy.engine import RowMapping
from sqlalchemy.ext.asyncio import AsyncSession

from certsapi.stats.projection import progress_statuses


class StatsRepository:
    """Executes scalar COUNT queries and the per-log aggregation query."""

    def __init__(
        self,
        session: AsyncSession,
        ctpool_settings: CtPoolSettings | None = None,
    ) -> None:
        self._session = session
        self._ctpool_settings = ctpool_settings

    async def total_hostnames(self) -> int:
        """Return the total number of unique hostnames."""
        result = await self._session.execute(select(func.count()).select_from(Hostname))
        return int(result.scalar_one())

    async def total_certificates(self) -> int:
        """Return the total number of unique certificates."""
        result = await self._session.execute(
            select(func.count()).select_from(Certificate)
        )
        return int(result.scalar_one())

    async def total_logs(self) -> int:
        """Return the total number of known CT log sources."""
        result = await self._session.execute(
            select(func.count()).select_from(CtLogSource)
        )
        return int(result.scalar_one())

    async def total_ct_observations(self) -> int:
        """Return the total number of recorded CT observations."""

        result = await self._session.execute(
            select(func.count()).select_from(CtLogObservation)
        )
        return int(result.scalar_one())

    async def total_certificate_hostnames(self) -> int:
        """Return the total certificate-hostname join rows."""

        result = await self._session.execute(
            select(func.count()).select_from(CertificateHostname)
        )
        return int(result.scalar_one())

    async def get_active_instance_settings(self) -> CtInstanceSettings | None:
        """Return the most-recently-updated instance settings row, or None."""
        result = await self._session.execute(
            select(CtInstanceSettings)
            .order_by(CtInstanceSettings.updated_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_latest_snapshot(self, snapshot_type: str) -> dict | None:
        """Return the payload of the most recent snapshot of *snapshot_type*.

        Returns ``None`` when the ``ct_stats_snapshots`` table does not exist
        yet (pre-migration) or contains no rows of the requested type.

        Args:
            snapshot_type: Logical label, e.g. ``"full"``.

        Returns:
            The ``payload_json`` dict, or ``None``.
        """
        import json

        from ctpool.models.stats_snapshot import CtStatsSnapshot

        try:
            stmt = (
                select(CtStatsSnapshot)
                .where(CtStatsSnapshot.snapshot_type == snapshot_type)
                .order_by(CtStatsSnapshot.generated_at.desc())
                .limit(1)
            )
            result = await self._session.execute(stmt)
            row = result.scalar_one_or_none()
        except Exception:
            return None
        if row is None:
            return None
        payload = row.payload_json
        if isinstance(payload, str):
            return json.loads(payload)  # type: ignore[no-any-return]
        return payload  # type: ignore[return-value]

    async def get_snapshot_age_seconds(self, snapshot_type: str) -> float | None:
        """Return seconds since the most recent snapshot was generated.

        Returns ``None`` when no snapshot exists for *snapshot_type* or the
        table is not yet available.

        Args:
            snapshot_type: Logical label, e.g. ``"full"``.
        """
        from datetime import UTC, datetime

        from ctpool.models.stats_snapshot import CtStatsSnapshot

        try:
            stmt = (
                select(CtStatsSnapshot.generated_at)
                .where(CtStatsSnapshot.snapshot_type == snapshot_type)
                .order_by(CtStatsSnapshot.generated_at.desc())
                .limit(1)
            )
            result = await self._session.execute(stmt)
            generated_at = result.scalar_one_or_none()
        except Exception:
            return None
        if generated_at is None:
            return None
        now = datetime.now(UTC)
        return (now - generated_at.replace(tzinfo=UTC)).total_seconds()

    async def db_storage(self) -> RowMapping:
        """Return total DB size and per-table sizes using pg_* system functions."""
        stmt = text("""
            SELECT
                current_database() AS db_name,
                pg_database_size(current_database()) AS total_size_bytes,
                pg_size_pretty(
                    pg_database_size(current_database())
                ) AS total_size_pretty
        """)
        total_row = (await self._session.execute(stmt)).mappings().one()

        table_stmt = text("""
            SELECT
                relname AS table_name,
                n_live_tup AS row_estimate,
                pg_total_relation_size(relid) AS size_bytes,
                pg_size_pretty(pg_total_relation_size(relid)) AS size_pretty
            FROM pg_stat_user_tables
            ORDER BY size_bytes DESC
        """)
        table_rows = list((await self._session.execute(table_stmt)).mappings().all())
        return {"total": total_row, "tables": table_rows}  # type: ignore[return-value]

    async def backfill_observation_progress(self) -> RowMapping:
        """Return planned and processed observation totals across backfill ranges."""

        range_size = CtLogBackfillRange.end_index - CtLogBackfillRange.start_index + 1
        bounded_next = func.least(
            CtLogBackfillRange.next_index,
            CtLogBackfillRange.end_index + 1,
        )
        partial_complete = func.greatest(
            0,
            bounded_next - CtLogBackfillRange.start_index,
        )
        completed = case(
            (CtLogBackfillRange.status == "complete", range_size),
            (CtLogBackfillRange.status.in_(progress_statuses()), partial_complete),
            else_=0,
        )
        stmt = select(
            func.coalesce(func.sum(range_size), 0).label("planned_observations_total"),
            func.coalesce(func.sum(completed), 0).label(
                "planned_observations_completed"
            ),
        )
        return (await self._session.execute(stmt)).mappings().one()

    async def per_log_stats(self) -> list[RowMapping]:
        """Return per-log aggregated stats: tail position, backfill pct, sync time."""
        stmt = (
            select(
                CtLogSource.id,
                CtLogSource.description,
                CtLogSource.url,
                CtLogSource.log_state,
                CtLogTailCursor.next_index.label("tail_position"),
                CtLogTailCursor.updated_at.label("last_tail_sync"),
                func.count(CtLogBackfillRange.id)
                .filter(CtLogBackfillRange.status == "complete")
                .label("complete_ranges"),
                func.count(CtLogBackfillRange.id).label("total_ranges"),
            )
            .outerjoin(
                CtLogTailCursor,
                CtLogTailCursor.log_source_id == CtLogSource.id,
            )
            .outerjoin(
                CtLogBackfillRange,
                CtLogBackfillRange.log_source_id == CtLogSource.id,
            )
            .group_by(
                CtLogSource.id,
                CtLogSource.description,
                CtLogSource.url,
                CtLogSource.log_state,
                CtLogTailCursor.next_index,
                CtLogTailCursor.updated_at,
            )
            .order_by(CtLogSource.description)
        )
        result = await self._session.execute(stmt)
        return list(result.mappings().all())

    async def db_contention_snapshot(self) -> DbContentionOperatorSnapshot:
        """Return the normalized shared DB contention status."""

        return await read_db_contention_operator_snapshot(
            self._session,
            self._ctpool_settings,
        )

    async def ingestion_rate_stats(
        self,
        window_seconds_list: list[int],
    ) -> list[RowMapping]:
        """Return aggregated ingestion totals for each requested time window."""
        rows: list[RowMapping] = []
        now = datetime.now(UTC)
        for window_seconds in window_seconds_list:
            cutoff = now - timedelta(seconds=window_seconds)
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
            result = (await self._session.execute(stmt)).mappings().one()
            rows.append({"window_seconds": window_seconds, **dict(result)})  # type: ignore[arg-type]
        return rows

    async def tail_freshness_summary(
        self,
        stale_threshold_seconds: int = 300,
    ) -> RowMapping:
        """Return oldest lag, median lag, and stale count across all tail cursors.

        Cursors with ``updated_at IS NULL`` (created but never processed by a
        tail worker) are counted as stale — they are not fresh by definition.
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
                       OR EXTRACT(EPOCH FROM (now() - updated_at))
                          > :threshold
                ) AS stale_log_count
            FROM ct_log_tail_cursors
        """)
        return (
            (await self._session.execute(stmt, {"threshold": stale_threshold_seconds}))
            .mappings()
            .one()
        )

    async def entry_outcome_counts(self) -> dict[str, int]:
        """Return per-outcome row counts from ``ct_entry_outcomes``."""
        stmt = select(CtEntryOutcome.outcome, func.count().label("cnt")).group_by(
            CtEntryOutcome.outcome
        )
        result = await self._session.execute(stmt)
        counts: dict[str, int] = dict.fromkeys(ALL_OUTCOMES, 0)
        for row in result:
            counts[row.outcome] = int(row.cnt)
        return counts

    async def backfill_range_status_counts(
        self, claim_timeout_seconds: int
    ) -> dict[str, int]:
        """Return backfill range status counts, splitting stale in_progress separately.

        A range is considered stale when
        ``COALESCE(heartbeat_at, claimed_at) < now() - claim_timeout_seconds``.
        """
        cutoff = datetime.now(UTC) - timedelta(seconds=claim_timeout_seconds)
        stale_condition = (
            func.coalesce(
                CtLogBackfillRange.heartbeat_at, CtLogBackfillRange.claimed_at
            )
            < cutoff
        )

        stmt = select(
            func.count()
            .filter(CtLogBackfillRange.status == "pending")
            .label("pending"),
            func.count()
            .filter(
                CtLogBackfillRange.status == "in_progress",
                ~stale_condition,
            )
            .label("in_progress"),
            func.count()
            .filter(
                CtLogBackfillRange.status == "in_progress",
                stale_condition,
            )
            .label("stale_in_progress"),
            func.count()
            .filter(CtLogBackfillRange.status == "complete")
            .label("completed"),
            func.count().filter(CtLogBackfillRange.status == "failed").label("failed"),
        ).select_from(CtLogBackfillRange)
        result = await self._session.execute(stmt)
        row = result.one()
        return {
            "pending": int(row.pending),
            "in_progress": int(row.in_progress),
            "stale_in_progress": int(row.stale_in_progress),
            "completed": int(row.completed),
            "failed": int(row.failed),
        }

    async def ingestion_metrics_summary(self) -> dict[str, object]:
        """Return ingestion_metrics row count and oldest snapshot timestamp."""
        stmt = select(
            func.count().label("row_count"),
            func.min(IngestionMetric.snapshot_at).label("oldest_at"),
        ).select_from(IngestionMetric)
        result = await self._session.execute(stmt)
        row = result.one()
        return {
            "row_count": int(row.row_count),
            "oldest_at": row.oldest_at,
        }

    async def audit_health_counts(self) -> dict[str, int]:
        """Return count of open audit findings per severity."""
        stmt = select(
            func.count(case((CtAuditFinding.severity == SEVERITY_CRITICAL, 1))).label(
                "critical"
            ),
            func.count(case((CtAuditFinding.severity == SEVERITY_ERROR, 1))).label(
                "error"
            ),
            func.count(case((CtAuditFinding.severity == SEVERITY_WARNING, 1))).label(
                "warning"
            ),
            func.count(case((CtAuditFinding.severity == SEVERITY_INFO, 1))).label(
                "info"
            ),
        ).where(CtAuditFinding.status == STATUS_OPEN)
        result = await self._session.execute(stmt)
        row = result.one()
        return {
            "critical": int(row.critical or 0),
            "error": int(row.error or 0),
            "warning": int(row.warning or 0),
            "info": int(row.info or 0),
        }
