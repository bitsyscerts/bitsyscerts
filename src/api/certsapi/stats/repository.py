"""Ingestion statistics database queries."""

from __future__ import annotations

from ctpool.config import Settings as CtPoolSettings
from ctpool.db_contention_observability import read_db_contention_operator_snapshot
from ctpool.db_contention_types import DbContentionOperatorSnapshot
from ctpool.models.certificate import Certificate
from ctpool.models.certificate_hostname import CertificateHostname
from ctpool.models.hostname import Hostname
from ctpool.models.log_backfill_range import CtLogBackfillRange
from ctpool.models.log_source import CtLogSource
from ctpool.models.log_tail_cursor import CtLogTailCursor
from ctpool.models.observation import CtLogObservation
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
