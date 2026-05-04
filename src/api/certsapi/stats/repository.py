"""Ingestion statistics database queries."""

from __future__ import annotations

from ctpool.models.certificate import Certificate
from ctpool.models.hostname import Hostname
from ctpool.models.log_backfill_range import CtLogBackfillRange
from ctpool.models.log_source import CtLogSource
from ctpool.models.log_tail_cursor import CtLogTailCursor
from sqlalchemy import func, select
from sqlalchemy.engine import RowMapping
from sqlalchemy.ext.asyncio import AsyncSession


class StatsRepository:
    """Executes scalar COUNT queries and the per-log aggregation query."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

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
