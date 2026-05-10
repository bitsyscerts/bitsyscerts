"""Stats service: assembles global and per-log ingestion statistics.

# NOTE (201-500 line warning zone): This module consolidates all stats assembly
# and builder helpers in one place.  All helpers serve one endpoint and share
# model types.  Splitting would create multiple files that only make sense as
# a group.  Resolve by extracting if a second stats endpoint is added.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Protocol, cast

from sqlalchemy.engine import RowMapping

from certsapi.stats.models import (
    AuditHealth,
    BackfillHealth,
    BackfillRangeStats,
    DbContentionStats,
    EntryOutcomeStats,
    IngestionRateStats,
    IngestionRateWindow,
    LogStatsItem,
    MetricsRetentionStats,
    SnapshotMetadata,
    StatsResponse,
    StorageProfileSettings,
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

_logger = logging.getLogger(__name__)
_INGESTION_RATE_WINDOWS = [300, 3600]
_TAIL_STALE_THRESHOLD_SECONDS = 300
_SNAPSHOT_TYPE = "full"


class CtPoolSettingsLike(Protocol):
    """Subset of ctpool settings used by the stats service."""

    ct_backfill_claim_timeout_seconds: int
    ct_backfill_dispatch_mode: str
    ct_metrics_retention_days: int
    ct_stats_heavy_refresh_seconds: int


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


def _build_ingestion_rate_stats(
    rows: Sequence[Mapping[str, object]],
) -> IngestionRateStats:
    """Convert per-window aggregation rows to an IngestionRateStats instance.

    Sprint 5B populates precise throughput, uniqueness, and error rates from
    producer-written ``ingestion_metrics`` counters rather than leaving them
    null at the API layer.
    """
    windows: list[IngestionRateWindow] = []
    for row in rows:
        secs = _as_int(row["window_seconds"])
        minutes = secs / 60.0
        observations_per_sec = _as_float(row["entries_fetched"]) / secs
        observations_per_min = _as_float(row["entries_fetched"]) / minutes
        certs_per_min = _as_float(row["entries_parsed"]) / minutes
        hostnames_per_min = _as_float(row["hostnames_upserted"]) / minutes
        windows.append(
            IngestionRateWindow(
                window_seconds=secs,
                observations_per_sec=observations_per_sec,
                certs_per_min=certs_per_min,
                hostnames_per_min=hostnames_per_min,
                observations_per_min=observations_per_min,
                certificates_parsed_per_min=certs_per_min,
                new_unique_certificates_per_min=(
                    _as_float(row["new_unique_certificates"]) / minutes
                ),
                duplicate_certificates_per_min=(
                    _as_float(row["duplicate_certificates"]) / minutes
                ),
                hostnames_observed_per_min=hostnames_per_min,
                new_unique_hostnames_per_min=(
                    _as_float(row["new_unique_hostnames"]) / minutes
                ),
                known_hostnames_per_min=_as_float(row["known_hostnames"]) / minutes,
                retryable_errors_per_min=_as_float(row["retryable_errors"]) / minutes,
                terminal_entry_errors_per_min=(
                    _as_float(row["terminal_entry_errors"]) / minutes
                ),
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


def _build_audit_health(counts: dict[str, int]) -> AuditHealth:
    """Build an AuditHealth summary from per-severity open finding counts."""
    total = sum(counts.values())
    actionable = counts.get("critical", 0) + counts.get("error", 0)
    status = "attention_needed" if actionable > 0 else "ok"
    return AuditHealth(
        open_critical=counts.get("critical", 0),
        open_error=counts.get("error", 0),
        open_warning=counts.get("warning", 0),
        open_info=counts.get("info", 0),
        total_open=total,
        status=status,  # type: ignore[arg-type]
    )


def _build_backfill_health(failed: int, stale: int) -> BackfillHealth:
    """Derive a BackfillHealth summary from range status counts."""
    if failed > 0 and stale > 0:
        msg = (
            f"{failed} backfill range(s) have failed and require retry or inspection. "
            f"{stale} range(s) are stale in-progress."
        )
    elif failed > 0:
        msg = f"{failed} backfill range(s) have failed and require retry or inspection."
    elif stale > 0:
        msg = f"{stale} range(s) are stuck in_progress with no recent heartbeat."
    else:
        msg = ""
    status: str = "warning" if (failed > 0 or stale > 0) else "ok"
    return BackfillHealth(
        status=status,  # type: ignore[arg-type]
        failed_ranges=failed,
        stale_ranges=stale,
        message=msg,
    )


def _resolve_backfill_range_mode(
    ctpool_settings: CtPoolSettingsLike | None,
) -> tuple[str, bool]:
    """Return live backfill-range mode metadata for API responses.

    Live range counts come from the legacy ``ct_log_backfill_ranges`` table.
    When per-log dispatch is active, those counts are retained only as a
    secondary compatibility view and must not be treated as the primary
    operator signal.
    """

    dispatch_mode = "per-log"
    if ctpool_settings is not None:
        dispatch_mode = ctpool_settings.ct_backfill_dispatch_mode
    return dispatch_mode, dispatch_mode != "per-log"


def _coerce_oldest_metric_at(value: object) -> datetime | None:
    """Return a datetime payload field only when the row value is one."""

    return value if isinstance(value, datetime) else None


def _as_int(value: object) -> int:
    """Coerce repository scalar values to ints for stats responses."""

    return int(value) if isinstance(value, int | float) else 0


def _as_float(value: object) -> float:
    """Coerce repository scalar values to floats for rate calculations."""

    return float(value) if isinstance(value, int | float) else 0.0


class StatsService:
    """Runs all stats queries sequentially and assembles the StatsResponse."""

    def __init__(self, repository: StatsRepository) -> None:
        self._repository = repository

    async def get_stats(self) -> StatsResponse:
        """Return aggregated ingestion statistics.

        Attempts to serve a recently-computed snapshot from ``ct_stats_snapshots``
        when one is available and fresh (age < ``ct_stats_heavy_refresh_seconds``).
        Falls back to running all live queries when no fresh snapshot exists.

        Always attaches :class:`SnapshotMetadata` so the dashboard can show
        the operator how fresh the displayed numbers are and whether the
        payload is stale (Sprint 5).
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

    @staticmethod
    def _build_snapshot_meta(
        *,
        age_seconds: float | None,
        source: str,
    ) -> SnapshotMetadata:
        """Build :class:`SnapshotMetadata` honouring the configured stale window."""
        from certsapi.config import get_settings

        threshold = int(get_settings().stats_stale_seconds)
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

    async def _try_get_fresh_snapshot(self) -> dict | None:
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

    async def _get_stats_live(self) -> StatsResponse:
        """Run all live queries and build a StatsResponse from scratch."""
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
        dispatch_mode, backfill_ranges_primary = _resolve_backfill_range_mode(
            ctpool_settings
        )
        metrics_summary = await self._repository.ingestion_metrics_summary()
        audit_counts = await self._repository.audit_health_counts()
        retention_days = (
            ctpool_settings.ct_metrics_retention_days
            if ctpool_settings is not None
            else 30
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
        active_settings = cast(
            ActiveSettingsLike | None,
            await self._repository.get_active_instance_settings(),
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
            active_settings=active_settings,
        )
        storage_profile_block = _build_storage_profile_block(active_settings)
        return StatsResponse(
            total_hostnames=total_h,
            storage_profile=storage_profile_block,
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
            ingestion_rate=_build_ingestion_rate_stats(
                cast(Sequence[Mapping[str, object]], rate_rows)
            ),
            tail_freshness=_build_tail_freshness_stats(
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
            backfill_health=_build_backfill_health(
                failed=backfill_counts["failed"],
                stale=backfill_counts["stale_in_progress"],
            ),
            metrics_retention=MetricsRetentionStats(
                ingestion_metrics_rows=_as_int(metrics_summary.get("row_count")),
                oldest_ingestion_metric_at=_coerce_oldest_metric_at(
                    metrics_summary.get("oldest_at")
                ),
                metrics_retention_days=retention_days,
            ),
            audit_health=_build_audit_health(audit_counts),
            logs=[_row_to_log_item(row, now) for row in per_log],
        )


def _build_storage_profile_block(
    active_settings: ActiveSettingsLike | None,
) -> StorageProfileSettings | None:
    """Convert an active settings row to StorageProfileSettings or None."""
    if active_settings is None:
        return None
    return StorageProfileSettings(
        storage_profile=active_settings.storage_profile,
        cert_storage_mode=active_settings.cert_storage_mode,
        hostname_retention_mode=active_settings.hostname_retention_mode,
        backfill_days=active_settings.backfill_days,
        cert_retention_days=active_settings.cert_retention_days,
        observation_retention_days=active_settings.observation_retention_days,
        entry_outcome_retention_days=active_settings.entry_outcome_retention_days,
        metrics_retention_days=active_settings.metrics_retention_days,
        settings_hash=active_settings.settings_hash,
        source="database",
    )
