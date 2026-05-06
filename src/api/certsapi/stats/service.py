"""Stats service: assembles global and per-log ingestion statistics."""

from __future__ import annotations

from sqlalchemy.engine import RowMapping

from certsapi.stats.models import (
    LogStatsItem,
    StatsResponse,
    StorageStats,
    TableStorageItem,
)
from certsapi.stats.projection import (
    ProjectionInputs,
    compute_storage_projection,
    read_disk_safety_snapshot,
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
        total_o = await self._repository.total_ct_observations()
        total_ch = await self._repository.total_certificate_hostnames()
        per_log = await self._repository.per_log_stats()
        progress = await self._repository.backfill_observation_progress()
        storage_data = await self._repository.db_storage()
        total_size_bytes = int(storage_data["total"]["total_size_bytes"])
        storage = StorageStats(
            total_size_bytes=total_size_bytes,
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
        storage_projection = compute_storage_projection(
            ProjectionInputs(
                database_size_bytes=total_size_bytes,
                ct_observations_count=total_o,
                certificates_count=total_c,
                hostnames_count=total_h,
                certificate_hostnames_count=total_ch,
                planned_observations_total=int(progress["planned_observations_total"]),
                planned_observations_completed=int(
                    progress["planned_observations_completed"]
                ),
            ),
            disk_snapshot=read_disk_safety_snapshot(),
        )
        return StatsResponse(
            total_hostnames=total_h,
            total_certificates=total_c,
            total_logs=total_l,
            storage=storage,
            storage_projection=storage_projection,
            logs=[_row_to_log_item(row) for row in per_log],
        )
