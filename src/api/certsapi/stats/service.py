"""Stats service: assembles global and per-log ingestion statistics.

NOTE (201-500 line warning zone): The StatsService._get_stats_live method
is inherently wide — it runs ~15 independent queries and maps each to a
model.  A further split into a QueryRunner + Assembler pair is deferred
until a second stats consumer is added.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any, Protocol, cast

from sqlalchemy.engine import RowMapping

from certsapi.stats.models import (
    BackfillRangeStats,
    BackfillStateSummary,
    DbContentionStats,
    EntryOutcomeStats,
    SnapshotMetadata,
    StatsResponse,
    StorageStats,
    TableStorageItem,
    WorkerSummary,
)
from certsapi.stats.projection import (
    ProjectionInputs,
    compute_storage_projection,
    read_disk_safety_snapshot,
)
from certsapi.stats.repository import StatsRepository
from certsapi.stats.response_builders import (
    build_audit_health,
    build_backfill_health,
    build_ingestion_health,
    build_ingestion_rate_stats,
    build_maintenance_status,
    build_metrics_retention,
    build_storage_profile_block,
    build_tail_freshness_stats,
    resolve_backfill_range_mode,
    row_to_log_item,
)

_logger = logging.getLogger(__name__)
_INGESTION_RATE_WINDOWS = [300, 3600]
_TAIL_STALE_THRESHOLD_SECONDS = 300
_SNAPSHOT_TYPE = "full"


class CtPoolSettingsLike(Protocol):
    """Subset of ctpool settings used by the stats service."""

    ct_backfill_claim_timeout_seconds: int
    ct_backfill_dispatch_mode: str
    ct_metrics_retention_days: int
    ct_maintenance_interval_seconds: int
    ct_stats_heavy_refresh_seconds: int
    ct_worker_stale_seconds: int


class ActiveSettingsLike(Protocol):
    """Subset of instance settings exposed in the stats payload."""

    storage_profile: str
    cert_storage_mode: str
    hostname_retention_mode: str
    backfill_days: int
    cert_retention_days: int
    observation_retention_days: int
    entry_outcome_retention_days: int
    metrics_retention_days: int
    settings_hash: str


class StatsService:
    """Runs all stats queries sequentially and assembles the StatsResponse."""

    def __init__(
        self,
        repository: StatsRepository,
        *,
        stats_stale_seconds: int = 120,
    ) -> None:
        self._repository = repository
        self._stats_stale_seconds = stats_stale_seconds

    async def get_stats(self) -> StatsResponse:
        """Return aggregated ingestion statistics.

        Attempts to serve a recently-computed snapshot from ``ct_stats_snapshots``
        when one is available and fresh (age < ``ct_stats_heavy_refresh_seconds``).
        Falls back to running all live queries when no fresh snapshot exists.

        Always attaches :class:`SnapshotMetadata` so the dashboard can show
        the operator how fresh the displayed numbers are and whether the
        payload is stale.
        """
        snapshot_age = await self._snapshot_age_safe()
        snapshot_payload = await self._try_get_fresh_snapshot()
        if snapshot_payload is not None:
            try:
                response = StatsResponse.model_validate(snapshot_payload)
                response.snapshot = self._build_snapshot_meta(
                    age_seconds=snapshot_age,
                    source="snapshot",
                )
                return response
            except Exception:
                _logger.warning(
                    "Failed to validate cached stats snapshot; falling back to live"
                )

        live_response = await self._get_stats_live()
        live_response.snapshot = self._build_snapshot_meta(
            age_seconds=snapshot_age,
            source="live" if snapshot_age is not None else "none",
        )
        return live_response

    async def _snapshot_age_safe(self) -> float | None:
        """Read snapshot age without raising; returns None on any failure."""
        try:
            value = await self._repository.get_snapshot_age_seconds(_SNAPSHOT_TYPE)
        except Exception:
            return None
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _build_snapshot_meta(
        self,
        *,
        age_seconds: float | None,
        source: str,
    ) -> SnapshotMetadata:
        """Build :class:`SnapshotMetadata` honouring the configured stale window."""
        threshold = int(self._stats_stale_seconds)
        is_stale = age_seconds is not None and age_seconds > threshold
        generated_at: datetime | None = None
        if age_seconds is not None:
            now = datetime.now(UTC)
            generated_at = datetime.fromtimestamp(now.timestamp() - age_seconds, tz=UTC)
        return SnapshotMetadata(
            generated_at=generated_at,
            age_seconds=age_seconds,
            is_stale=bool(is_stale),
            stale_threshold_seconds=threshold,
            source=source,  # type: ignore[arg-type]
        )

    async def _try_get_fresh_snapshot(self) -> dict[str, Any] | None:
        """Return snapshot payload if one exists and is fresh.

        Fresh means younger than ``ct_stats_heavy_refresh_seconds`` (default 300 s).
        Returns ``None`` when no fresh snapshot is available.
        """
        ctpool_settings = cast(
            CtPoolSettingsLike | None,
            self._repository._ctpool_settings,
        )
        max_age = (
            ctpool_settings.ct_stats_heavy_refresh_seconds
            if ctpool_settings is not None
            else 300
        )
        try:
            age = await self._repository.get_snapshot_age_seconds(_SNAPSHOT_TYPE)
            if age is None or age > max_age:
                return None
            return await self._repository.get_latest_snapshot(_SNAPSHOT_TYPE)
        except Exception:
            return None

    async def _resolve_projection_inputs(
        self,
        total_o: int,
        total_c: int,
        total_h: int,
        total_ch: int,
        total_size_bytes: int,
        progress: RowMapping,
    ) -> ProjectionInputs:
        """Build projection inputs, falling back to CT log tree sizes.

        Falls back to CT log tree sizes when no backfill ranges exist.
        """
        planned_total = int(progress["planned_observations_total"])
        planned_completed = int(progress["planned_observations_completed"])
        if planned_total == 0:
            try:
                ct_progress = await self._repository.ct_log_progress_totals()
                planned_total = ct_progress["planned_total"]
                planned_completed = ct_progress["planned_completed"]
            except Exception:
                _logger.warning(
                    "ct_log_progress_totals query failed; projection may be limited"
                )
        return ProjectionInputs(
            database_size_bytes=total_size_bytes,
            ct_observations_count=total_o,
            certificates_count=total_c,
            hostnames_count=total_h,
            certificate_hostnames_count=total_ch,
            planned_observations_total=planned_total,
            planned_observations_completed=planned_completed,
        )

    async def _get_stats_live(self) -> StatsResponse:
        """Run all live queries and build a StatsResponse from scratch.

        NOTE (21-50 warning): this method is necessarily wide — it must run
        ~15 independent queries and map each result to a model field.  Each
        line maps to a distinct query; extracting sub-methods would add
        indirection without reducing complexity.
        """
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
        outcome_counts = await self._repository.entry_outcome_counts()
        ctpool_settings = cast(
            CtPoolSettingsLike | None,
            self._repository._ctpool_settings,
        )
        claim_timeout = (
            ctpool_settings.ct_backfill_claim_timeout_seconds
            if ctpool_settings is not None
            else 1800
        )
        backfill_counts = await self._repository.backfill_range_status_counts(
            claim_timeout
        )
        dispatch_mode, backfill_ranges_primary = resolve_backfill_range_mode(
            ctpool_settings
        )
        worker_stale_seconds = (
            ctpool_settings.ct_worker_stale_seconds
            if ctpool_settings is not None
            else 300
        )
        maintenance_interval_seconds = (
            ctpool_settings.ct_maintenance_interval_seconds
            if ctpool_settings is not None
            else 3600
        )
        worker_summary = await self._repository.worker_summary(worker_stale_seconds)
        backfill_state_summary = await self._repository.backfill_state_summary(
            worker_stale_seconds
        )
        maintenance_run = await self._repository.latest_maintenance_run()
        metrics_summary = await self._repository.ingestion_metrics_summary()
        audit_counts = await self._repository.audit_health_counts()
        retention_days = (
            ctpool_settings.ct_metrics_retention_days
            if ctpool_settings is not None
            else 30
        )
        total_size_bytes = int(storage_data["total"]["total_size_bytes"])
        active_settings = cast(
            ActiveSettingsLike | None,
            await self._repository.get_active_instance_settings(),
        )
        projection_inputs = await self._resolve_projection_inputs(
            total_o, total_c, total_h, total_ch, total_size_bytes, progress
        )
        storage_projection = compute_storage_projection(
            projection_inputs,
            disk_snapshot=read_disk_safety_snapshot(),
            active_settings=active_settings,
        )
        return StatsResponse(
            total_hostnames=total_h,
            storage_profile=build_storage_profile_block(active_settings),
            total_certificates=total_c,
            total_logs=total_l,
            storage=StorageStats(
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
            ),
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
            ingestion_rate=build_ingestion_rate_stats(
                cast(Sequence[Mapping[str, object]], rate_rows)
            ),
            tail_freshness=build_tail_freshness_stats(
                freshness_row, _TAIL_STALE_THRESHOLD_SECONDS
            ),
            entry_outcomes=EntryOutcomeStats(
                stored=outcome_counts.get("stored", 0),
                parse_error=outcome_counts.get("parse_error", 0),
                unsupported_entry_type=outcome_counts.get("unsupported_entry_type", 0),
                skipped_by_policy=outcome_counts.get("skipped_by_policy", 0),
            ),
            backfill_ranges=BackfillRangeStats(
                pending=backfill_counts["pending"],
                in_progress=backfill_counts["in_progress"],
                stale_in_progress=backfill_counts["stale_in_progress"],
                completed=backfill_counts["completed"],
                failed=backfill_counts["failed"],
                dispatch_mode=dispatch_mode,
                is_primary=backfill_ranges_primary,
            ),
            backfill_health=build_backfill_health(
                failed=backfill_counts["failed"],
                stale=backfill_counts["stale_in_progress"],
            ),
            metrics_retention=build_metrics_retention(metrics_summary, retention_days),
            audit_health=build_audit_health(audit_counts),
            logs=[row_to_log_item(row, now) for row in per_log],
            workers=WorkerSummary.model_validate(worker_summary),
            backfill_state=BackfillStateSummary.model_validate(
                {
                    **backfill_state_summary,
                    "dispatch_mode": dispatch_mode,
                    "is_primary": dispatch_mode == "per-log",
                }
            ),
            ingestion_health=build_ingestion_health(
                backfill_state_summary,
                worker_summary,
                outcome_counts,
            ),
            maintenance=build_maintenance_status(
                maintenance_run,
                interval_seconds=maintenance_interval_seconds,
                active_settings=active_settings,
            ),
        )
