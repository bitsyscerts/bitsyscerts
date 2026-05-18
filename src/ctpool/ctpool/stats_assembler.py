"""Assembles a stats payload dict from raw query results and settings.

Accepts dicts produced by :mod:`ctpool.stats_queries` and an optional
``CtInstanceSettings`` row.  Returns a plain Python dict that matches the
``StatsResponse`` Pydantic model accepted by the API.

This module has no dependency on certsapi — it can be used by the ctpool
snapshotting worker without importing the API package.

NOTE (201-500 line warning zone): Each builder function is a single-purpose
dict factory for one stats card.  Splitting across many files would fragment
closely related output shapes.  Resolve by extracting per-domain builder
packages when a second consumer is added.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ctpool.models.instance_settings import CtInstanceSettings

_logger = logging.getLogger(__name__)

_TAIL_STALE_THRESHOLD_SECONDS = 300


def assemble_stats_payload(
    *,
    global_counts: dict[str, int],
    database_size_bytes: int,
    backfill_progress: dict[str, int],
    backfill_status_counts: dict[str, int],
    storage_data: dict[str, Any],
    contention_snapshot: Any,
    rate_rows: list[dict[str, Any]],
    freshness_row: dict[str, Any],
    outcome_counts: dict[str, int],
    metrics_summary: dict[str, Any],
    audit_counts: dict[str, int],
    per_log_rows: list[dict[str, Any]],
    active_settings: CtInstanceSettings | None,
    now: datetime | None = None,
    worker_summary: dict[str, Any] | None = None,
    backfill_state: dict[str, Any] | None = None,
    maintenance_run: dict[str, Any] | None = None,
    maintenance_interval_seconds: int = 3600,
    dispatch_mode: str = "per-log",
    ct_log_progress: dict[str, int] | None = None,
    host_capacity: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a stats payload dict from pre-fetched query results.

    Args:
        global_counts: Output of query_global_counts.
        database_size_bytes: Total database size in bytes.
        backfill_progress: Output of query_backfill_planned_counts.
        backfill_status_counts: Output of query_backfill_range_status_counts.
        storage_data: Dict with ``total`` and ``tables`` keys.
        contention_snapshot: DbContentionState ORM row or compatible object.
        rate_rows: Output of query_ingestion_rate_windows.
        freshness_row: Output of query_tail_freshness.
        outcome_counts: Output of query_entry_outcome_counts.
        metrics_summary: Output of query_ingestion_metrics_summary.
        audit_counts: Per-severity open audit finding counts.
        per_log_rows: Output of query_log_stats.
        active_settings: Active CtInstanceSettings row, or None.
        now: Timestamp to use as "now" (defaults to datetime.now(UTC)).
        worker_summary: Optional worker summary dict.
        backfill_state: Optional per-log backfill state dict.
        maintenance_run: Optional latest maintenance run dict.
        maintenance_interval_seconds: Seconds between scheduled maintenance runs.
        dispatch_mode: Active backfill dispatch mode string.
        ct_log_progress: Output of query_ct_log_progress_totals; fallback
            for projection when backfill_progress.planned_total is zero.
        host_capacity: Output of collect_host_capacity, or None.

    Returns:
        A dict that can be validated against StatsResponse.
    """
    if now is None:
        now = datetime.now(UTC)

    sections = _collect_sections(
        global_counts=global_counts,
        database_size_bytes=database_size_bytes,
        backfill_progress=backfill_progress,
        backfill_status_counts=backfill_status_counts,
        storage_data=storage_data,
        contention_snapshot=contention_snapshot,
        rate_rows=rate_rows,
        freshness_row=freshness_row,
        outcome_counts=outcome_counts,
        metrics_summary=metrics_summary,
        audit_counts=audit_counts,
        per_log_rows=per_log_rows,
        active_settings=active_settings,
        now=now,
        worker_summary=worker_summary,
        backfill_state=backfill_state,
        maintenance_run=maintenance_run,
        maintenance_interval_seconds=maintenance_interval_seconds,
        dispatch_mode=dispatch_mode,
        ct_log_progress=ct_log_progress,
        host_capacity=host_capacity,
    )
    return {
        "total_hostnames": global_counts["hostnames"],
        "total_certificates": global_counts["certificates"],
        "total_logs": len(per_log_rows),
        **sections,
    }


def _collect_sections(
    *,
    global_counts: dict[str, int],
    database_size_bytes: int,
    backfill_progress: dict[str, int],
    backfill_status_counts: dict[str, int],
    storage_data: dict[str, Any],
    contention_snapshot: Any,
    rate_rows: list[dict[str, Any]],
    freshness_row: dict[str, Any],
    outcome_counts: dict[str, int],
    metrics_summary: dict[str, Any],
    audit_counts: dict[str, int],
    per_log_rows: list[dict[str, Any]],
    active_settings: Any,
    now: datetime,
    worker_summary: dict[str, Any] | None,
    backfill_state: dict[str, Any] | None,
    maintenance_run: dict[str, Any] | None,
    maintenance_interval_seconds: int,
    dispatch_mode: str,
    ct_log_progress: dict[str, int] | None,
    host_capacity: dict[str, Any] | None,
) -> dict[str, Any]:
    """Build every named section dict and return them keyed by section name.

    NOTE (21-50 warning): this coordinator is necessarily dense — it wires
    ~15 independent sections that share no sub-dependencies among themselves.
    """
    from ctpool.stats_maintenance_builder import build_maintenance_dict
    from ctpool.stats_projection_builder import build_projection_dict

    metrics_retention_days = (
        active_settings.metrics_retention_days if active_settings is not None else 30
    )
    total_size_bytes = int(storage_data["total"]["total_size_bytes"])
    per_log_primary = dispatch_mode == "per-log"

    if backfill_state is not None:
        backfill_state = {
            **backfill_state,
            "dispatch_mode": dispatch_mode,
            "is_primary": per_log_primary,
        }

    backfill_ranges_dict = _build_backfill_ranges_dict(backfill_status_counts)
    backfill_ranges_dict["dispatch_mode"] = dispatch_mode
    backfill_ranges_dict["is_primary"] = not per_log_primary

    return {
        "storage_profile": _build_storage_profile_dict(active_settings),
        "storage": _build_storage_dict(storage_data, total_size_bytes),
        "storage_projection": build_projection_dict(
            global_counts=global_counts,
            database_size_bytes=total_size_bytes,
            backfill_progress=backfill_progress,
            active_settings=active_settings,
            ct_log_progress=ct_log_progress,
        ),
        "db_contention": _build_contention_dict(contention_snapshot),
        "ingestion_rate": {"windows": _build_ingestion_rate_list(rate_rows)},
        "tail_freshness": _build_freshness_dict(freshness_row),
        "entry_outcomes": _build_entry_outcomes_dict(outcome_counts),
        "backfill_ranges": backfill_ranges_dict,
        "backfill_health": _build_backfill_health_dict(
            backfill_status_counts["failed"],
            backfill_status_counts["stale_in_progress"],
        ),
        "metrics_retention": {
            "ingestion_metrics_rows": int(metrics_summary["row_count"]),
            "oldest_ingestion_metric_at": metrics_summary["oldest_at"],
            "metrics_retention_days": metrics_retention_days,
        },
        "audit_health": _build_audit_health_dict(audit_counts),
        "logs": [_build_log_item_dict(row, now) for row in per_log_rows],
        "workers": worker_summary,
        "backfill_state": backfill_state,
        "ingestion_health": _build_ingestion_health_dict(
            backfill_state, worker_summary, outcome_counts
        ),
        "maintenance": build_maintenance_dict(
            maintenance_run, maintenance_interval_seconds, active_settings
        ),
        "host_capacity": host_capacity,
    }


def _build_storage_dict(
    storage_data: dict[str, Any],
    total_size_bytes: int,
) -> dict[str, Any]:
    """Build the storage sub-dict from db_storage query output."""
    return {
        "total_size_bytes": total_size_bytes,
        "total_size_pretty": storage_data["total"]["total_size_pretty"],
        "tables": [
            {
                "table_name": row["table_name"],
                "row_estimate": int(row["row_estimate"]),
                "size_bytes": int(row["size_bytes"]),
                "size_pretty": row["size_pretty"],
            }
            for row in storage_data["tables"]
        ],
    }


def _build_contention_dict(contention: Any) -> dict[str, Any]:
    """Convert a contention snapshot object to a plain dict."""
    return {
        "status": contention.status,
        "degraded_mode_active": contention.degraded_mode_active,
        "pressure_ema": contention.pressure_ema,
        "base_sleep_seconds": contention.base_sleep_seconds,
        "shared_batch_size_cap": contention.shared_batch_size_cap,
        "effective_batch_size_cap": contention.effective_batch_size_cap,
        "updated_at": contention.updated_at,
        "notes": list(contention.notes),
        "total_retryable_errors": contention.total_retryable_errors,
        "retryable_errors_per_min_5min": contention.retryable_errors_per_min_5min,
    }


def _build_ingestion_rate_list(
    rate_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Convert raw rate rows to the ingestion_rate windows list format."""
    windows = []
    for row in rate_rows:
        secs = int(row["window_seconds"])
        minutes = secs / 60.0
        obs_pm = float(row["entries_fetched"]) / minutes
        certs_pm = float(row["entries_parsed"]) / minutes
        hosts_pm = float(row["hostnames_upserted"]) / minutes
        windows.append(
            {
                "window_seconds": secs,
                "observations_per_sec": float(row["entries_fetched"]) / secs,
                "certs_per_min": certs_pm,
                "hostnames_per_min": hosts_pm,
                "observations_per_min": obs_pm,
                "certificates_parsed_per_min": certs_pm,
                "new_unique_certificates_per_min": (
                    float(row["new_unique_certificates"]) / minutes
                ),
                "duplicate_certificates_per_min": (
                    float(row["duplicate_certificates"]) / minutes
                ),
                "hostnames_observed_per_min": hosts_pm,
                "new_unique_hostnames_per_min": (
                    float(row["new_unique_hostnames"]) / minutes
                ),
                "known_hostnames_per_min": float(row["known_hostnames"]) / minutes,
                "retryable_errors_per_min": (float(row["retryable_errors"]) / minutes),
                "terminal_entry_errors_per_min": (
                    float(row["terminal_entry_errors"]) / minutes
                ),
            }
        )
    return windows


def _build_freshness_dict(row: dict[str, Any]) -> dict[str, Any]:
    """Build tail_freshness sub-dict from the query row."""
    return {
        "stale_threshold_seconds": _TAIL_STALE_THRESHOLD_SECONDS,
        "stale_log_count": int(row.get("stale_log_count") or 0),
        "oldest_lag_seconds": (
            int(row["oldest_lag_seconds"])
            if row.get("oldest_lag_seconds") is not None
            else None
        ),
        "median_lag_seconds": (
            int(row["median_lag_seconds"])
            if row.get("median_lag_seconds") is not None
            else None
        ),
    }


def _build_entry_outcomes_dict(counts: dict[str, int]) -> dict[str, int]:
    """Build entry_outcomes sub-dict from raw outcome counts."""
    return {
        "stored": counts.get("stored", 0),
        "parse_error": counts.get("parse_error", 0),
        "unsupported_entry_type": counts.get("unsupported_entry_type", 0),
        "skipped_by_policy": counts.get("skipped_by_policy", 0),
    }


def _build_backfill_ranges_dict(counts: dict[str, int]) -> dict[str, Any]:
    """Build backfill_ranges sub-dict from status counts."""
    return {
        "pending": counts["pending"],
        "in_progress": counts["in_progress"],
        "stale_in_progress": counts["stale_in_progress"],
        "completed": counts["completed"],
        "failed": counts["failed"],
    }


def _build_backfill_health_dict(failed: int, stale: int) -> dict[str, Any]:
    """Build backfill_health sub-dict from failed/stale counts."""
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
    return {
        "status": "warning" if (failed > 0 or stale > 0) else "ok",
        "failed_ranges": failed,
        "stale_ranges": stale,
        "message": msg,
    }


def _build_storage_profile_dict(active_settings: Any) -> dict[str, Any] | None:
    """Build storage_profile sub-dict from active settings, or None."""
    if active_settings is None:
        return None
    return {
        "storage_profile": active_settings.storage_profile,
        "cert_storage_mode": active_settings.cert_storage_mode,
        "hostname_retention_mode": active_settings.hostname_retention_mode,
        "backfill_days": active_settings.backfill_days,
        "cert_retention_days": active_settings.cert_retention_days,
        "observation_retention_days": active_settings.observation_retention_days,
        "entry_outcome_retention_days": active_settings.entry_outcome_retention_days,
        "metrics_retention_days": active_settings.metrics_retention_days,
        "settings_hash": active_settings.settings_hash,
        "source": "database",
    }


def _build_audit_health_dict(counts: dict[str, int]) -> dict[str, Any]:
    """Build audit_health sub-dict from per-severity counts."""
    total = sum(counts.values())
    actionable = counts.get("critical", 0) + counts.get("error", 0)
    return {
        "open_critical": counts.get("critical", 0),
        "open_error": counts.get("error", 0),
        "open_warning": counts.get("warning", 0),
        "open_info": counts.get("info", 0),
        "total_open": total,
        "status": "attention_needed" if actionable > 0 else "ok",
    }


def _build_ingestion_health_dict(
    backfill_state: dict[str, Any] | None,
    worker_summary: dict[str, Any] | list[Any] | None,
    outcome_counts: dict[str, int] | None,
) -> dict[str, Any]:
    """Build the ingestion_health summary card dict.

    NOTE (21-50 warning): many independent counters are gathered from three
    different input dicts; extraction would only produce trivial helpers.
    """
    retrying = rate_limited = paused = error_logs = degraded = 0
    total_retryable = total_terminal = 0
    if backfill_state is not None:
        retrying = int(backfill_state.get("retrying") or 0)
        rate_limited = int(backfill_state.get("rate_limited") or 0)
        paused = int(backfill_state.get("paused") or 0)
        degraded = int(backfill_state.get("degraded") or 0)
        error_logs = int(backfill_state.get("error") or 0)
        for item in backfill_state.get("items") or []:
            total_retryable += int(item.get("retryable_error_count") or 0)
            total_terminal += int(item.get("terminal_error_count") or 0)

    stale_workers = (
        int(worker_summary.get("stale") or 0) if isinstance(worker_summary, dict) else 0
    )

    recent_terminal = 0
    if outcome_counts is not None:
        for key in ("parse_error", "unsupported_entry_type", "write_error"):
            recent_terminal += int(outcome_counts.get(key) or 0)

    return {
        "retrying_logs": retrying,
        "rate_limited_logs": rate_limited,
        "paused_logs": paused,
        "degraded_logs": degraded,
        "error_logs": error_logs,
        "stale_workers": stale_workers,
        "retryable_error_total": total_retryable,
        "terminal_error_total": total_terminal,
        "recent_terminal_outcomes": recent_terminal,
        "status": "attention_needed" if (paused > 0 or error_logs > 0) else "ok",
    }


def _build_log_item_dict(row: dict[str, Any], now: datetime) -> dict[str, Any]:
    """Convert a per-log row to the LogStatsItem dict format."""
    total: int = int(row.get("total_ranges") or 0)
    complete: int = int(row.get("complete_ranges") or 0)
    pct = (complete / total * 100.0) if total > 0 else None
    last_sync = row.get("last_tail_sync")
    lag: int | None = None
    if last_sync is not None and hasattr(last_sync, "replace"):
        lag = max(0, int((now - last_sync.replace(tzinfo=UTC)).total_seconds()))
    return {
        "log_id": str(row["id"]),
        "description": row["description"],
        "url": row["url"],
        "log_state": row["log_state"],
        "tail_position": row.get("tail_position"),
        "last_tail_sync": last_sync,
        "backfill_complete_pct": pct,
        "tail_freshness_lag_seconds": lag,
    }
