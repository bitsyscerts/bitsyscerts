"""Maintenance card dict builders for the stats assembler.

Exports:
    build_maintenance_dict — top-level maintenance card dispatcher.
"""

from __future__ import annotations

from typing import Any


def build_maintenance_never_ran_dict(profile: str | None) -> dict[str, Any]:
    """Return the maintenance card dict for the never_ran case."""
    return {
        "status": "never_ran",
        "active_profile": profile,
        "last_prune_started_at": None,
        "last_prune_completed_at": None,
        "last_prune_status": None,
        "last_prune_mode": None,
        "last_prune_deleted": {
            "certificates": 0,
            "certificate_hostnames": 0,
            "observations": 0,
            "entry_outcomes": 0,
            "ingestion_metrics": 0,
        },
        "preserved_hostnames": None,
        "duration_ms": None,
        "next_prune_due_at": None,
        "is_enforced": False,
        "error_message": None,
    }


def build_maintenance_from_run_dict(
    maintenance_run: dict[str, Any],
    interval_seconds: int,
    profile: str | None,
) -> dict[str, Any]:
    """Return the maintenance card dict from a non-null maintenance run row."""
    from ctpool.maintenance_queries import compute_next_due, is_lite_enforced

    next_due = compute_next_due(maintenance_run.get("started_at"), interval_seconds)
    enforced = is_lite_enforced(maintenance_run, interval_seconds=interval_seconds)
    return {
        "status": maintenance_run.get("status", "unknown"),
        "active_profile": maintenance_run.get("storage_profile") or profile,
        "last_prune_started_at": maintenance_run.get("started_at"),
        "last_prune_completed_at": maintenance_run.get("completed_at"),
        "last_prune_status": maintenance_run.get("status"),
        "last_prune_mode": maintenance_run.get("mode"),
        "last_prune_deleted": maintenance_run.get("deleted")
        or {
            "certificates": 0,
            "certificate_hostnames": 0,
            "observations": 0,
            "entry_outcomes": 0,
            "ingestion_metrics": 0,
        },
        "preserved_hostnames": maintenance_run.get("preserved_hostnames"),
        "duration_ms": maintenance_run.get("duration_ms"),
        "next_prune_due_at": next_due,
        "is_enforced": enforced,
        "error_message": maintenance_run.get("error_message"),
    }


def build_maintenance_dict(
    maintenance_run: dict[str, Any] | None,
    interval_seconds: int,
    active_settings: Any,
) -> dict[str, Any]:
    """Dispatch to the correct maintenance card builder."""
    profile = active_settings.storage_profile if active_settings is not None else None
    if maintenance_run is None:
        return build_maintenance_never_ran_dict(profile)
    return build_maintenance_from_run_dict(maintenance_run, interval_seconds, profile)
