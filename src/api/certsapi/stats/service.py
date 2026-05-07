"""Stats service: assembles global and per-log ingestion statistics."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.engine import RowMapping

from certsapi.stats.models import (
    DbContentionStats,
    IngestionRateStats,
    IngestionRateWindow,
    LogStatsItem,
    StatsResponse,
    StorageStats,
    TableStorageItem,
    TailFreshnessStats,
)
from certsapi.stats.projection import (
    ProjectionInputs,
    compute_storage_projection,
    read_disk_safety_snapshot,
)
from certsapi.stats.repository import StatsRepository

_INGESTION_RATE_WINDOWS = [300, 3600]
_TAIL_STALE_THRESHOLD_SECONDS = 300


def _row_to_log_item(row: RowMapping, now: datetime) -> LogStatsItem:
    """Convert a per-log aggregation row to a LogStatsItem response model."""
    total: int = row["total_ranges"]
    complete: int = row["complete_ranges"]
    pct = (complete / total * 100.0) if total > 0 else None
    last_sync: datetime | None = row["last_tail_sync"]
    lag: int | None = None
    if last_sync is not None:
        lag = max(0, int((now - last_sync.replace(tzinfo=UTC)).total_seconds()))
    return LogStatsItem(
        log_id=row["id"],
        description=row["description"],
        url=row["url"],
        log_state=row["log_state"],
        tail_position=row["tail_position"],
        last_tail_sync=row["last_tail_sync"],
        backfill_complete_pct=pct,
        tail_freshness_lag_seconds=lag,
    )


def _build_ingestion_rate_stats(rows: list[RowMapping]) -> IngestionRateStats:
    """Convert per-window aggregation rows to an IngestionRateStats instance."""
    windows: list[IngestionRateWindow] = []
    for row in rows:
        secs = int(row["window_seconds"])
        minutes = secs / 60.0
        windows.append(
            IngestionRateWindow(
                window_seconds=secs,
                observations_per_sec=float(row["entries_fetched"]) / secs,
                certs_per_min=float(row["certs_upserted"]) / minutes,
                hostnames_per_min=float(row["hostnames_upserted"]) / minutes,
            )
        )
    return IngestionRateStats(windows=windows)


def _build_tail_freshness_stats(
    row: RowMapping,
    stale_threshold_seconds: int,
) -> TailFreshnessStats:
    """Convert the tail freshness aggregate row to a TailFreshnessStats instance."""
    return TailFreshnessStats(
        stale_threshold_seconds=stale_threshold_seconds,
        stale_log_count=int(row["stale_log_count"] or 0),
        oldest_lag_seconds=int(row["oldest_lag_seconds"])
        if row["oldest_lag_seconds"] is not None
        else None,
        median_lag_seconds=int(row["median_lag_seconds"])
        if row["median_lag_seconds"] is not None
        else None,
    )


class StatsService:
    """Runs all stats queries sequentially and assembles the StatsResponse."""

    def __init__(self, repository: StatsRepository) -> None:
        self._repository = repository

    async def get_stats(self) -> StatsResponse:
        """Return aggregated ingestion statistics."""
        now = datetime.now(UTC)
        total_h = await self._repository.total_hostnames()
        total_c = await self._repository.total_certificates()
        total_l = await self._repository.total_logs()
        total_o = await self._repository.total_ct_observations()
        total_ch = await self._repository.total_certificate_hostnames()
        per_log = await self._repository.per_log_stats()
        progress = await self._repository.backfill_observation_progress()
        storage_data = await self._repository.db_storage()
        contention = await self._repository.db_contention_snapshot()
        rate_rows = await self._repository.ingestion_rate_stats(_INGESTION_RATE_WINDOWS)
        freshness_row = await self._repository.tail_freshness_summary(
            _TAIL_STALE_THRESHOLD_SECONDS
        )
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
            db_contention=DbContentionStats(
                status=contention.status,
                degraded_mode_active=contention.degraded_mode_active,
                pressure_ema=contention.pressure_ema,
                base_sleep_seconds=contention.base_sleep_seconds,
                shared_batch_size_cap=contention.shared_batch_size_cap,
                effective_batch_size_cap=contention.effective_batch_size_cap,
                updated_at=contention.updated_at,
                notes=list(contention.notes),
                total_retryable_errors=contention.total_retryable_errors,
                retryable_errors_per_min_5min=contention.retryable_errors_per_min_5min,
            ),
            ingestion_rate=_build_ingestion_rate_stats(rate_rows),
            tail_freshness=_build_tail_freshness_stats(
                freshness_row, _TAIL_STALE_THRESHOLD_SECONDS
            ),
            logs=[_row_to_log_item(row, now) for row in per_log],
        )
