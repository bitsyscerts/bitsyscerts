"""Stats service: assembles global and per-log ingestion statistics."""

from __future__ import annotations

from sqlalchemy.engine import RowMapping

from certsapi.stats.models import (
    LogStatsItem,
    StorageStats,
    StatsResponse,
    TableStorageItem,
)
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
    """Runs all stats queries sequentially and assembles the StatsResponse."""

    def __init__(self, repository: StatsRepository) -> None:
        self._repository = repository

    async def get_stats(self) -> StatsResponse:
        """Return aggregated ingestion statistics."""
        total_h = await self._repository.total_hostnames()
        total_c = await self._repository.total_certificates()
        total_l = await self._repository.total_logs()
        per_log = await self._repository.per_log_stats()
        storage_data = await self._repository.db_storage()
        storage = StorageStats(
            total_size_bytes=storage_data["total"]["total_size_bytes"],
            total_size_pretty=storage_data["total"]["total_size_pretty"],
            tables=[
                TableStorageItem(
                    table_name=row["table_name"],
                    row_estimate=int(row["row_estimate"]),
                    size_bytes=int(row["size_bytes"]),
                    size_pretty=row["size_pretty"],
                )
                for row in storage_data["tables"]
            ],
        )
        return StatsResponse(
            total_hostnames=total_h,
            total_certificates=total_c,
            total_logs=total_l,
            storage=storage,
            logs=[_row_to_log_item(row) for row in per_log],
        )
