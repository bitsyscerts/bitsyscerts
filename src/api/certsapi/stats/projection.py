"""Projection helpers for estimated CT sync progress and storage growth.

# NOTE (201-500 line warning zone): This module consolidates all projection
# computation paths in one place.  The profile-aware path and the linear
# fallback path are closely coupled.  Splitting them would require passing
# profile results between modules.  Resolve if either path exceeds 100 lines.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from pydantic import ValidationError

from certsapi.stats.models import (
    IngestionWorkload,
    StorageProjection,
    StorageProjectionCategoryBreakdown,
)

if TYPE_CHECKING:
    from ctpool.models.instance_settings import CtInstanceSettings

_BYTES_PER_GIB = 1024**3
_PROGRESS_STATUSES = frozenset({"claimed", "in_progress", "partial", "running"})
ProjectionStatus = Literal[
    "available",
    "insufficient_backfill_plan",
    "insufficient_observations",
]


@dataclass(frozen=True)
class ProjectionInputs:
    """Current counters used to compute a storage projection."""

    database_size_bytes: int
    ct_observations_count: int
    certificates_count: int
    hostnames_count: int
    certificate_hostnames_count: int
    planned_observations_total: int
    planned_observations_completed: int


@dataclass(frozen=True)
class DiskSnapshot:
    """Filesystem capacity snapshot for the PostgreSQL volume."""

    total_bytes: int
    used_bytes: int
    free_bytes: int
    min_free_bytes: int


def progress_statuses() -> tuple[str, ...]:
    """Return statuses that imply partial observation progress."""

    return tuple(sorted(_PROGRESS_STATUSES))


def compute_storage_projection(
    inputs: ProjectionInputs,
    disk_snapshot: DiskSnapshot | None = None,
    active_settings: CtInstanceSettings | None = None,
) -> StorageProjection:
    """Build a conservative storage projection from current counts.

    When ``active_settings`` is provided, also runs the profile-aware
    category-estimate projection and includes the breakdown in the response.
    """

    completed = _clamp_completed(
        inputs.planned_observations_completed,
        inputs.planned_observations_total,
    )
    remaining = max(inputs.planned_observations_total - completed, 0)
    base = _projection_base(inputs, completed, remaining)
    profile_fields = _profile_aware_fields(inputs, active_settings)
    if inputs.planned_observations_total <= 0:
        return _unavailable_projection(
            "insufficient_backfill_plan",
            base,
            "Storage projection unavailable. Backfill ranges are not available yet.",
            profile_fields,
        )
    if inputs.ct_observations_count <= 0:
        return _unavailable_projection(
            "insufficient_observations",
            base,
            (
                "Storage projection unavailable. Observation counts are not "
                "available yet."
            ),
            profile_fields,
        )
    return _available_projection(
        inputs, completed, remaining, base, disk_snapshot, profile_fields
    )


def _profile_aware_fields(
    inputs: ProjectionInputs,
    active_settings: CtInstanceSettings | None,
) -> dict[str, object]:
    """Return profile_basis, profile, and category_breakdown fields.

    Returns an empty dict if no active_settings are provided.
    """
    if active_settings is None:
        return {}
    try:
        from ctpool.profile_projection import compute_profile_aware_projection

        result = compute_profile_aware_projection(
            profile=active_settings.storage_profile,
            cert_storage_mode=active_settings.cert_storage_mode,
            hostname_count=inputs.hostnames_count,
            cert_count=inputs.certificates_count,
            obs_count=inputs.ct_observations_count,
            cert_hostname_count=inputs.certificate_hostnames_count,
            backfill_days=active_settings.backfill_days,
            cert_retention_days=active_settings.cert_retention_days,
            observation_retention_days=active_settings.observation_retention_days,
            entry_outcome_retention_days=active_settings.entry_outcome_retention_days,
        )
        breakdown = StorageProjectionCategoryBreakdown(
            hostname_index_bytes=result.hostname_index_bytes,
            certificate_metadata_bytes=result.certificate_metadata_bytes,
            certificate_public_key_bytes=result.certificate_public_key_bytes,
            raw_cert_der_bytes=result.raw_cert_der_bytes,
            ct_observations_bytes=result.ct_observations_bytes,
            entry_outcomes_bytes=result.entry_outcomes_bytes,
            cert_hostname_relationships_bytes=result.cert_hostname_relationships_bytes,
            metrics_and_ops_bytes=result.metrics_and_ops_bytes,
            index_overhead_bytes=result.index_overhead_bytes,
        )
        return {
            "projection_basis": "profile_aware_category_estimate",
            "profile": result.profile,
            "category_breakdown": breakdown,
            "_profile_total_bytes": result.projected_total_bytes,
        }
    except Exception:  # pragma: no cover — defensive; never fails in prod
        return {}


def read_disk_safety_snapshot() -> DiskSnapshot | None:
    """Return filesystem capacity for the configured PostgreSQL volume path."""

    try:
        from ctpool.config import get_settings as get_ctpool_settings

        settings = get_ctpool_settings()
        usage = shutil.disk_usage(settings.ct_disk_check_path)
    except (FileNotFoundError, OSError, PermissionError, ValidationError):
        return None
    return DiskSnapshot(
        total_bytes=int(usage.total),
        used_bytes=int(usage.used),
        free_bytes=int(usage.free),
        min_free_bytes=int(settings.ct_min_free_disk_gb * _BYTES_PER_GIB),
    )


def _clamp_completed(completed: int, total: int) -> int:
    """Clamp completed observations into the planned range."""

    return max(0, min(completed, max(total, 0)))


def _projection_base(
    inputs: ProjectionInputs,
    completed: int,
    remaining: int,
) -> dict[str, int]:
    """Return shared projection fields used by available and unavailable states."""

    return {
        "database_size_bytes": inputs.database_size_bytes,
        "ct_observations_count": inputs.ct_observations_count,
        "certificates_count": inputs.certificates_count,
        "hostnames_count": inputs.hostnames_count,
        "certificate_hostnames_count": inputs.certificate_hostnames_count,
        "planned_observations_total": inputs.planned_observations_total,
        "planned_observations_completed": completed,
        "planned_observations_remaining": remaining,
    }


def _unavailable_projection(
    status: ProjectionStatus,
    base: dict[str, int],
    note: str,
    profile_fields: dict[str, object] | None = None,
) -> StorageProjection:
    """Return a projection payload when required inputs are unavailable."""

    payload: dict[str, object] = {
        **base,
        **{k: v for k, v in (profile_fields or {}).items() if not k.startswith("_")},
        "status": status,
        "sync_percent_by_observation": None,
        "bytes_per_observation_current": None,
        "projected_remaining_database_size_bytes": None,
        "projected_final_database_size_bytes": None,
        "storage_percent_of_projected": None,
        "projection_low_bytes": None,
        "projection_current_bytes": None,
        "projection_high_bytes": None,
        "notes": [note],
    }
    return StorageProjection.model_validate(payload)


def _available_projection(
    inputs: ProjectionInputs,
    completed: int,
    remaining: int,
    base: dict[str, int],
    disk_snapshot: DiskSnapshot | None,
    profile_fields: dict[str, object] | None = None,
) -> StorageProjection:
    """Return a projection payload when planning and observation counts exist."""

    bytes_per_observation = inputs.database_size_bytes / inputs.ct_observations_count

    # Use profile-aware projected retained total when available, so Lite mode
    # does not report a 25+ TB projection based on all future CT observations.
    profile_total = (
        profile_fields.get("_profile_total_bytes") if profile_fields else None
    )
    if profile_total is not None:
        projected_remaining = max(int(profile_total) - inputs.database_size_bytes, 0)
        projected_final = int(profile_total)
        try:
            from ctpool.profile_projection import compute_projection_confidence

            confidence: object = compute_projection_confidence(
                inputs.ct_observations_count
            )
        except ImportError:  # pragma: no cover
            confidence = None
    else:
        projected_remaining = int(round(remaining * bytes_per_observation))
        projected_final = inputs.database_size_bytes + projected_remaining
        confidence = None

    ingestion_workload = _build_ingestion_workload(inputs, completed, remaining)
    notes = [
        (
            "Projection is based on current bytes per CT observation and "
            "will improve as more data is ingested."
        ),
        "Storage percentage is an estimate, not authoritative sync progress.",
    ]
    disk_fields = _disk_projection_fields(
        disk_snapshot,
        projected_remaining,
        projected_final,
        notes,
    )
    payload: dict[str, object] = {
        **base,
        **disk_fields,
        **{k: v for k, v in (profile_fields or {}).items() if not k.startswith("_")},
        "status": "available",
        "confidence": confidence,
        "ingestion_workload": ingestion_workload,
        "sync_percent_by_observation": completed / inputs.planned_observations_total,
        "bytes_per_observation_current": bytes_per_observation,
        "projected_remaining_database_size_bytes": projected_remaining,
        "projected_final_database_size_bytes": projected_final,
        "storage_percent_of_projected": (
            inputs.database_size_bytes / projected_final
            if projected_final > 0
            else None
        ),
        "projection_low_bytes": int(projected_final * 0.75),
        "projection_current_bytes": projected_final,
        "projection_high_bytes": int(projected_final * 1.5),
        "notes": notes,
    }
    return StorageProjection.model_validate(payload)


def _build_ingestion_workload(
    inputs: ProjectionInputs,
    completed: int,
    remaining: int,
) -> IngestionWorkload:
    """Build an IngestionWorkload summary from projection inputs.

    Args:
        inputs: Current projection counter snapshot.
        completed: Clamped planned observations completed count.
        remaining: Planned observations remaining.

    Returns:
        An :class:`~certsapi.stats.models.IngestionWorkload` instance.
    """
    total = inputs.planned_observations_total
    sync_pct = (completed / total) if total > 0 else None
    return IngestionWorkload(
        planned_observations_total=total,
        planned_observations_completed=completed,
        planned_observations_remaining=remaining,
        sync_percent=sync_pct,
    )


def _disk_projection_fields(
    disk_snapshot: DiskSnapshot | None,
    projected_remaining: int,
    projected_final: int,
    notes: list[str],
) -> dict[str, int | float | bool | None]:
    """Return disk-capacity fields for the projection payload."""

    if disk_snapshot is None or projected_final <= 0:
        return {}
    projected_free_after = disk_snapshot.free_bytes - projected_remaining
    projected_fits = projected_free_after > disk_snapshot.min_free_bytes
    if projected_remaining > disk_snapshot.free_bytes:
        notes.append("Projected size may exceed available disk space.")
    elif not projected_fits:
        notes.append(
            "Projected final size leaves less than the configured minimum free disk."
        )
    return {
        "disk_total_bytes": disk_snapshot.total_bytes,
        "disk_used_bytes": disk_snapshot.used_bytes,
        "disk_free_bytes": disk_snapshot.free_bytes,
        "disk_free_percent": (
            disk_snapshot.free_bytes / disk_snapshot.total_bytes
            if disk_snapshot.total_bytes > 0
            else None
        ),
        "configured_min_free_disk_bytes": disk_snapshot.min_free_bytes,
        "projected_disk_free_after_sync_bytes": projected_free_after,
        "projected_fits_on_disk": projected_fits,
    }
