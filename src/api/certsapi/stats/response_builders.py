"""Stateless helper builders for certsapi stats responses.

All functions here are pure (no I/O) converters from raw query result
data to certsapi Pydantic model instances or plain values.  Extracted
from service.py to keep service.py under the 500-line defect threshold.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy.engine import RowMapping

from certsapi.stats.models import (
    AuditHealth,
    BackfillHealth,
    IngestionHealth,
    IngestionRateStats,
    IngestionRateWindow,
    LogStatsItem,
    MaintenanceStatus,
    MetricsRetentionStats,
    StorageProfileSettings,
    TailFreshnessStats,
)


def row_to_log_item(row: RowMapping, now: datetime) -> LogStatsItem:
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


def build_ingestion_rate_stats(
    rows: Sequence[Mapping[str, object]],
) -> IngestionRateStats:
    """Convert per-window aggregation rows to an IngestionRateStats instance."""
    windows: list[IngestionRateWindow] = []
    for row in rows:
        secs = _as_int(row["window_seconds"])
        minutes = secs / 60.0
        obs_ps = _as_float(row["entries_fetched"]) / secs
        obs_pm = _as_float(row["entries_fetched"]) / minutes
        certs_pm = _as_float(row["entries_parsed"]) / minutes
        hosts_pm = _as_float(row["hostnames_upserted"]) / minutes
        windows.append(
            IngestionRateWindow(
                window_seconds=secs,
                observations_per_sec=obs_ps,
                certs_per_min=certs_pm,
                hostnames_per_min=hosts_pm,
                observations_per_min=obs_pm,
                certificates_parsed_per_min=certs_pm,
                new_unique_certificates_per_min=(
                    _as_float(row["new_unique_certificates"]) / minutes
                ),
                duplicate_certificates_per_min=(
                    _as_float(row["duplicate_certificates"]) / minutes
                ),
                hostnames_observed_per_min=hosts_pm,
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


def build_tail_freshness_stats(
    row: RowMapping,
    stale_threshold_seconds: int,
) -> TailFreshnessStats:
    """Convert the tail freshness aggregate row to a TailFreshnessStats instance."""
    return TailFreshnessStats(
        stale_threshold_seconds=stale_threshold_seconds,
        stale_log_count=int(row["stale_log_count"] or 0),
        oldest_lag_seconds=(
            int(row["oldest_lag_seconds"])
            if row["oldest_lag_seconds"] is not None
            else None
        ),
        median_lag_seconds=(
            int(row["median_lag_seconds"])
            if row["median_lag_seconds"] is not None
            else None
        ),
    )


def build_audit_health(counts: dict[str, int]) -> AuditHealth:
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


def build_backfill_health(failed: int, stale: int) -> BackfillHealth:
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


def build_ingestion_health(
    backfill_state: dict[str, object] | None,
    worker_summary: dict[str, object] | None,
    outcome_counts: dict[str, int],
) -> IngestionHealth:
    """Build the dashboard ingestion-health summary for live responses."""
    retrying = rate_limited = paused = error_logs = degraded = 0
    total_retryable = total_terminal = 0
    if backfill_state is not None:
        retrying = _as_int(backfill_state.get("retrying"))
        rate_limited = _as_int(backfill_state.get("rate_limited"))
        paused = _as_int(backfill_state.get("paused"))
        degraded = _as_int(backfill_state.get("degraded"))
        error_logs = _as_int(backfill_state.get("error"))
        for item in cast(list[dict[str, object]], backfill_state.get("items") or []):
            total_retryable += _as_int(item.get("retryable_error_count"))
            total_terminal += _as_int(item.get("terminal_error_count"))

    stale_workers = 0
    if worker_summary is not None:
        stale_workers = _as_int(worker_summary.get("stale_total"))

    recent_terminal = sum(
        _as_int(outcome_counts.get(k))
        for k in ("parse_error", "unsupported_entry_type", "write_error")
    )
    return IngestionHealth(
        retrying_logs=retrying,
        rate_limited_logs=rate_limited,
        paused_logs=paused,
        degraded_logs=degraded,
        error_logs=error_logs,
        stale_workers=stale_workers,
        retryable_error_total=total_retryable,
        terminal_error_total=total_terminal,
        recent_terminal_outcomes=recent_terminal,
        status="attention_needed" if (paused > 0 or error_logs > 0) else "ok",
    )


def build_maintenance_status(
    maintenance_run: dict[str, object] | None,
    *,
    interval_seconds: int,
    active_settings: object | None,
) -> MaintenanceStatus:
    """Build the maintenance card block for live responses."""
    from ctpool.maintenance_queries import compute_next_due, is_lite_enforced

    profile = (
        active_settings.storage_profile  # type: ignore[attr-defined]
        if active_settings is not None
        else None
    )
    if maintenance_run is None:
        return MaintenanceStatus(
            status="never_ran",
            active_profile=profile,
            is_enforced=False,
        )
    return MaintenanceStatus(
        status=cast(str, maintenance_run.get("status", "unknown")),  # type: ignore[arg-type]
        active_profile=(
            cast(str | None, maintenance_run.get("storage_profile")) or profile
        ),
        last_prune_started_at=cast(datetime | None, maintenance_run.get("started_at")),
        last_prune_completed_at=cast(
            datetime | None, maintenance_run.get("completed_at")
        ),
        last_prune_status=cast(str | None, maintenance_run.get("status")),  # type: ignore[arg-type]
        last_prune_mode=cast(str | None, maintenance_run.get("mode")),  # type: ignore[arg-type]
        last_prune_deleted=cast(dict[str, int], maintenance_run.get("deleted") or {}),  # type: ignore[arg-type]
        preserved_hostnames=cast(
            int | None, maintenance_run.get("preserved_hostnames")
        ),
        duration_ms=cast(int | None, maintenance_run.get("duration_ms")),
        next_prune_due_at=compute_next_due(
            cast(datetime | None, maintenance_run.get("started_at")),
            interval_seconds,
        ),
        is_enforced=is_lite_enforced(
            maintenance_run,
            interval_seconds=interval_seconds,
        ),
        error_message=cast(str | None, maintenance_run.get("error_message")),
    )


def build_storage_profile_block(
    active_settings: object | None,
) -> StorageProfileSettings | None:
    """Convert an active settings row to StorageProfileSettings or None."""
    if active_settings is None:
        return None
    s: Any = active_settings
    return StorageProfileSettings(
        storage_profile=s.storage_profile,
        cert_storage_mode=s.cert_storage_mode,
        hostname_retention_mode=s.hostname_retention_mode,
        backfill_days=s.backfill_days,
        cert_retention_days=s.cert_retention_days,
        observation_retention_days=s.observation_retention_days,
        entry_outcome_retention_days=s.entry_outcome_retention_days,
        metrics_retention_days=s.metrics_retention_days,
        settings_hash=s.settings_hash,
        source="database",
    )


def build_metrics_retention(
    metrics_summary: dict[str, object],
    retention_days: int,
) -> MetricsRetentionStats:
    """Build the MetricsRetentionStats model from a summary row."""
    return MetricsRetentionStats(
        ingestion_metrics_rows=_as_int(metrics_summary.get("row_count")),
        oldest_ingestion_metric_at=coerce_datetime(metrics_summary.get("oldest_at")),
        metrics_retention_days=retention_days,
    )


def resolve_backfill_range_mode(
    ctpool_settings: object | None,
) -> tuple[str, bool]:
    """Return (dispatch_mode, backfill_ranges_is_primary) from settings."""
    dispatch_mode = "per-log"
    if ctpool_settings is not None:
        dispatch_mode = ctpool_settings.ct_backfill_dispatch_mode  # type: ignore[attr-defined]
    return dispatch_mode, dispatch_mode != "per-log"


def coerce_datetime(value: object) -> datetime | None:
    """Return a datetime payload field only when the row value is one."""
    return value if isinstance(value, datetime) else None


def _as_int(value: object) -> int:
    """Coerce repository scalar values to ints."""
    return int(value) if isinstance(value, int | float) else 0


def _as_float(value: object) -> float:
    """Coerce repository scalar values to floats."""
    return float(value) if isinstance(value, int | float) else 0.0
