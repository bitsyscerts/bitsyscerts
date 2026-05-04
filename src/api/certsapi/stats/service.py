"""Stats service: assembles global and per-log ingestion statistics."""

from __future__ import annotations

import asyncio

from sqlalchemy.engine import RowMapping

from certsapi.stats.models import LogStatsItem, StatsResponse
from certsapi.stats.repository import StatsRepository


def _row_to_log_item(row: RowMapping) -> LogStatsItem:
    """Convert a per-log aggregation row to a LogStatsItem response model."""
    total: int = row["total_ranges"]
    complete: int = row["complete_ranges"]
    pct = (complete / total * 100.0) if total > 0 else None
    return LogStatsItem(
        log_id=row["id"],
        description=row["description"],
        url=row["url"],
        log_state=row["log_state"],
        tail_position=row["tail_position"],
        last_tail_sync=row["last_tail_sync"],
        backfill_complete_pct=pct,
    )


class StatsService:
    """Runs all stats queries concurrently and assembles the StatsResponse."""

    def __init__(self, repository: StatsRepository) -> None:
        self._repository = repository

    async def get_stats(self) -> StatsResponse:
        """Return aggregated ingestion statistics."""
        (total_h, total_c, total_l), per_log = await asyncio.gather(
            self._counts(),
            self._repository.per_log_stats(),
        )
        return StatsResponse(
            total_hostnames=total_h,
            total_certificates=total_c,
            total_logs=total_l,
            logs=[_row_to_log_item(row) for row in per_log],
        )

    async def _counts(self) -> tuple[int, int, int]:
        """Fetch all three scalar counts concurrently."""
        results = await asyncio.gather(
            self._repository.total_hostnames(),
            self._repository.total_certificates(),
            self._repository.total_logs(),
        )
        return results[0], results[1], results[2]
