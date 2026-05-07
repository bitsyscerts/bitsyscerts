"""Assembles a stats payload dict from raw query results and settings.

Accepts dicts produced by :mod:`ctpool.stats_queries` and an optional
``CtInstanceSettings`` row.  Returns a plain Python dict that matches the
``StatsResponse`` Pydantic model accepted by the API.

This module has no dependency on certsapi — it can be used by the ctpool
snapshotting worker without importing the API package.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ctpool.models.instance_settings import CtInstanceSettings

_logger = logging.getLogger(__name__)

_TAIL_STALE_THRESHOLD_SECONDS = 300
_INGESTION_RATE_WINDOWS = [300, 3600]


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
) -> dict[str, Any]:
    """Build a stats payload dict from pre-fetched query results.

    Args:
        global_counts: Output of :func:`~ctpool.stats_queries.query_global_counts`.
        database_size_bytes: Total database size in bytes.
        backfill_progress: Output of backfill planned counts query.
        backfill_status_counts: Output of range status counts query.
        storage_data: Dict with ``total`` and ``tables`` keys (DB storage query).
        contention_snapshot: CtDbContentionState ORM row or compatible object.
        rate_rows: Output of ingestion rate windows query.
        freshness_row: Output of tail freshness query.
        outcome_counts: Output of entry outcome counts query.
        metrics_summary: Output of ingestion metrics summary query.
        audit_counts: Output of audit health counts query.
        per_log_rows: Output of per-log stats query.
        active_settings: Active ``CtInstanceSettings`` row, or ``None``.
        now: Timestamp to use as "now" (defaults to ``datetime.now(UTC)``).

    Returns:
        A dict that can be validated against ``StatsResponse``.
    """
    if now is None:
        now = datetime.now(UTC)

    metrics_retention_days = (
        active_settings.metrics_retention_days if active_settings is not None else 30
    )

    total_size_bytes = int(storage_data["total"]["total_size_bytes"])
    tables_list = [
        {
            "table_name": row["table_name"],
            "row_estimate": int(row["row_estimate"]),
            "size_bytes": int(row["size_bytes"]),
            "size_pretty": row["size_pretty"],
        }
        for row in storage_data["tables"]
    ]

    contention_dict = _build_contention_dict(contention_snapshot)
    rate_list = _build_ingestion_rate_list(rate_rows)
    freshness_dict = _build_freshness_dict(freshness_row)
    entry_outcomes_dict = _build_entry_outcomes_dict(outcome_counts)
    backfill_ranges_dict = _build_backfill_ranges_dict(backfill_status_counts)
    backfill_health_dict = _build_backfill_health_dict(
        backfill_status_counts["failed"],
        backfill_status_counts["stale_in_progress"],
    )
    storage_profile_dict = _build_storage_profile_dict(active_settings)
    logs_list = [_build_log_item_dict(row, now) for row in per_log_rows]

    return {
        "total_hostnames": global_counts["hostnames"],
        "total_certificates": global_counts["certificates"],
        "total_logs": len(per_log_rows),
        "storage_profile": storage_profile_dict,
        "storage": {
            "total_size_bytes": total_size_bytes,
            "total_size_pretty": storage_data["total"]["total_size_pretty"],
            "tables": tables_list,
        },
        "storage_projection": _build_projection_dict(
            global_counts=global_counts,
            database_size_bytes=total_size_bytes,
            backfill_progress=backfill_progress,
            active_settings=active_settings,
        ),
        "db_contention": contention_dict,
        "ingestion_rate": {"windows": rate_list},
        "tail_freshness": freshness_dict,
        "entry_outcomes": entry_outcomes_dict,
        "backfill_ranges": backfill_ranges_dict,
        "backfill_health": backfill_health_dict,
        "metrics_retention": {
            "ingestion_metrics_rows": int(metrics_summary["row_count"]),
            "oldest_ingestion_metric_at": metrics_summary["oldest_at"],
            "metrics_retention_days": metrics_retention_days,
        },
        "audit_health": _build_audit_health_dict(audit_counts),
        "logs": logs_list,
    }


def _build_projection_dict(
    *,
    global_counts: dict[str, int],
    database_size_bytes: int,
    backfill_progress: dict[str, int],
    active_settings: Any,
) -> dict[str, Any]:
    """Build the storage_projection sub-dict without importing certsapi.

    Uses only ctpool types so the snapshot worker has no API dependency.
    """
    try:
        from ctpool.profile_projection import (
            compute_profile_aware_projection,
            compute_projection_confidence,
        )
    except ImportError:
        _logger.warning("profile_projection unavailable; projection omitted")
        return {"status": "insufficient_backfill_plan", "notes": []}

    planned_total = backfill_progress.get("planned_total", 0)
    planned_completed = backfill_progress.get("planned_completed", 0)
    obs_count = global_counts["observations"]
    remaining = max(planned_total - planned_completed, 0)

    base: dict[str, Any] = {
        "database_size_bytes": database_size_bytes,
        "ct_observations_count": obs_count,
        "certificates_count": global_counts["certificates"],
        "hostnames_count": global_counts["hostnames"],
        "certificate_hostnames_count": global_counts["cert_hostnames"],
        "planned_observations_total": planned_total,
        "planned_observations_completed": min(planned_completed, planned_total),
        "planned_observations_remaining": remaining,
    }

    if planned_total <= 0:
        return {
            **base,
            "status": "insufficient_backfill_plan",
            "sync_percent_by_observation": None,
            "bytes_per_observation_current": None,
            "projected_remaining_database_size_bytes": None,
            "projected_final_database_size_bytes": None,
            "storage_percent_of_projected": None,
            "projection_low_bytes": None,
            "projection_current_bytes": None,
            "projection_high_bytes": None,
            "notes": [
                "Storage projection unavailable. Backfill ranges are not available yet."
            ],
        }

    if obs_count <= 0:
        return {
            **base,
            "status": "insufficient_observations",
            "sync_percent_by_observation": None,
            "bytes_per_observation_current": None,
            "projected_remaining_database_size_bytes": None,
            "projected_final_database_size_bytes": None,
            "storage_percent_of_projected": None,
            "projection_low_bytes": None,
            "projection_current_bytes": None,
            "projection_high_bytes": None,
            "notes": [
                "Storage projection unavailable. "
                "Observation counts are not available yet."
            ],
        }

    confidence = compute_projection_confidence(obs_count)
    profile_result = None
    category_breakdown: dict[str, Any] | None = None

    if active_settings is not None:
        try:
            profile_result = compute_profile_aware_projection(
                profile=active_settings.storage_profile,
                cert_storage_mode=active_settings.cert_storage_mode,
                hostname_count=global_counts["hostnames"],
                cert_count=global_counts["certificates"],
                obs_count=obs_count,
                cert_hostname_count=global_counts["cert_hostnames"],
                backfill_days=active_settings.backfill_days,
                cert_retention_days=active_settings.cert_retention_days,
                observation_retention_days=active_settings.observation_retention_days,
                entry_outcome_retention_days=(
                    active_settings.entry_outcome_retention_days
                ),
            )
            category_breakdown = {
                "hostname_index_bytes": profile_result.hostname_index_bytes,
                "certificate_metadata_bytes": (
                    profile_result.certificate_metadata_bytes
                ),
                "certificate_public_key_bytes": (
                    profile_result.certificate_public_key_bytes
                ),
                "raw_cert_der_bytes": profile_result.raw_cert_der_bytes,
                "ct_observations_bytes": profile_result.ct_observations_bytes,
                "entry_outcomes_bytes": profile_result.entry_outcomes_bytes,
                "cert_hostname_relationships_bytes": (
                    profile_result.cert_hostname_relationships_bytes
                ),
                "metrics_and_ops_bytes": profile_result.metrics_and_ops_bytes,
                "index_overhead_bytes": profile_result.index_overhead_bytes,
            }
        except Exception:
            _logger.warning("Profile projection failed; falling back to linear")

    # Use profile-aware total as the projected retained size
    if profile_result is not None:
        projected_final = profile_result.projected_total_bytes
        projected_remaining = max(projected_final - database_size_bytes, 0)
        bytes_per_obs = database_size_bytes / obs_count
        notes = list(profile_result.notes)
        projection_basis = "profile_aware_category_estimate"
        profile_name = profile_result.profile
    else:
        bytes_per_obs = database_size_bytes / obs_count
        projected_remaining = int(round(remaining * bytes_per_obs))
        projected_final = database_size_bytes + projected_remaining
        notes = [
            "Projection is based on current bytes per CT observation.",
        ]
        projection_basis = "linear_per_observation"
        profile_name = None

    sync_pct = (
        min(planned_completed, planned_total) / planned_total
        if planned_total > 0
        else None
    )
    storage_pct = database_size_bytes / projected_final if projected_final > 0 else None
    projection: dict[str, Any] = {
        **base,
        "status": "available",
        "confidence": confidence,
        "projection_basis": projection_basis,
        "sync_percent_by_observation": sync_pct,
        "bytes_per_observation_current": bytes_per_obs,
        "projected_remaining_database_size_bytes": projected_remaining,
        "projected_final_database_size_bytes": projected_final,
        "storage_percent_of_projected": storage_pct,
        "projection_low_bytes": int(projected_final * 0.75),
        "projection_current_bytes": projected_final,
        "projection_high_bytes": int(projected_final * 1.5),
        "notes": notes,
    }
    if profile_name is not None:
        projection["profile"] = profile_name
    if category_breakdown is not None:
        projection["category_breakdown"] = category_breakdown
    return projection


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
        windows.append(
            {
                "window_seconds": secs,
                "observations_per_sec": float(row["entries_fetched"]) / secs,
                "certs_per_min": float(row["certs_upserted"]) / minutes,
                "hostnames_per_min": float(row["hostnames_upserted"]) / minutes,
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


def _build_backfill_ranges_dict(counts: dict[str, int]) -> dict[str, int]:
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


def _build_storage_profile_dict(
    active_settings: Any,
) -> dict[str, Any] | None:
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


def _build_log_item_dict(
    row: dict[str, Any],
    now: datetime,
) -> dict[str, Any]:
    """Convert a per-log row to the LogStatsItem dict format."""
    total: int = int(row.get("total_ranges") or 0)
    complete: int = int(row.get("complete_ranges") or 0)
    pct = (complete / total * 100.0) if total > 0 else None
    last_sync = row.get("last_tail_sync")
    lag: int | None = None
    if last_sync is not None:
        if hasattr(last_sync, "replace"):
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
