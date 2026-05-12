"""Build the ``storage_projection`` sub-dict for stats snapshots.

Exports:
    build_projection_dict — assemble the storage_projection payload,
        using CT log tree-size totals as a fallback when no backfill
        plan exists (fresh installs or lite-mode deployments).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass

_logger = logging.getLogger(__name__)


def _resolve_effective_progress(
    backfill_progress: dict[str, int],
    ct_log_progress: dict[str, int] | None,
) -> tuple[int, int, str]:
    """Return (planned_total, planned_completed, projection_basis).

    Prefers backfill ranges when they have data.  Falls back to CT log
    tree-size totals when backfill ranges are empty and ct_log_progress
    is provided and non-zero.
    """
    bf_total = backfill_progress.get("planned_total", 0)
    bf_completed = backfill_progress.get("planned_completed", 0)
    if bf_total > 0:
        return bf_total, bf_completed, "backfill_ranges"

    if ct_log_progress is not None:
        ct_total = ct_log_progress.get("planned_total", 0)
        ct_completed = ct_log_progress.get("planned_completed", 0)
        if ct_total > 0:
            return ct_total, ct_completed, "ct_log_tree_sizes"

    return 0, 0, "none"


def _build_projection_base(
    global_counts: dict[str, int],
    database_size_bytes: int,
    planned_total: int,
    planned_completed: int,
) -> dict[str, Any]:
    """Return the static base fields present in every projection response."""
    remaining = max(planned_total - planned_completed, 0)
    return {
        "database_size_bytes": database_size_bytes,
        "ct_observations_count": global_counts["observations"],
        "certificates_count": global_counts["certificates"],
        "hostnames_count": global_counts["hostnames"],
        "certificate_hostnames_count": global_counts["cert_hostnames"],
        "planned_observations_total": planned_total,
        "planned_observations_completed": min(planned_completed, planned_total),
        "planned_observations_remaining": remaining,
    }


def _build_available_projection(
    base: dict[str, Any],
    database_size_bytes: int,
    obs_count: int,
    planned_total: int,
    planned_completed: int,
    confidence: str,
    projection_basis: str,
    profile_result: Any | None,
) -> dict[str, Any]:
    """Build the 'available' projection dict given optional profile result."""
    remaining = max(planned_total - planned_completed, 0)
    category_breakdown: dict[str, Any] | None = None

    if profile_result is not None:
        projected_final = profile_result.projected_total_bytes
        bytes_per_obs: float = database_size_bytes / obs_count if obs_count > 0 else 0.0
        notes = list(profile_result.notes)
        pb = "profile_aware_category_estimate"
        profile_name: str | None = profile_result.profile
        category_breakdown = {
            "hostname_index_bytes": profile_result.hostname_index_bytes,
            "certificate_metadata_bytes": profile_result.certificate_metadata_bytes,
            "certificate_public_key_bytes": profile_result.certificate_public_key_bytes,
            "raw_cert_der_bytes": profile_result.raw_cert_der_bytes,
            "ct_observations_bytes": profile_result.ct_observations_bytes,
            "entry_outcomes_bytes": profile_result.entry_outcomes_bytes,
            "cert_hostname_relationships_bytes": (
                profile_result.cert_hostname_relationships_bytes
            ),
            "metrics_and_ops_bytes": profile_result.metrics_and_ops_bytes,
            "index_overhead_bytes": profile_result.index_overhead_bytes,
        }
    else:
        bytes_per_obs = database_size_bytes / obs_count if obs_count > 0 else 0.0
        projected_remaining = int(round(remaining * bytes_per_obs))
        projected_final = database_size_bytes + projected_remaining
        notes = ["Projection is based on current bytes per CT observation."]
        pb = "linear_per_observation"
        profile_name = None

    projected_remaining = max(projected_final - database_size_bytes, 0)
    sync_pct = (
        min(planned_completed, planned_total) / planned_total
        if planned_total > 0
        else None
    )
    storage_pct = database_size_bytes / projected_final if projected_final > 0 else None

    result: dict[str, Any] = {
        **base,
        "status": "available",
        "confidence": confidence,
        "projection_basis": pb,
        "ct_log_tree_size_basis": projection_basis == "ct_log_tree_sizes",
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
        result["profile"] = profile_name
    if category_breakdown is not None:
        result["category_breakdown"] = category_breakdown
    return result


def _try_profile_projection(
    global_counts: dict[str, int],
    active_settings: Any,
) -> Any | None:
    """Return a ProfileAwareProjectionResult or None on any failure."""
    if active_settings is None:
        return None
    try:
        from ctpool.profile_projection import compute_profile_aware_projection

        return compute_profile_aware_projection(
            profile=active_settings.storage_profile,
            cert_storage_mode=active_settings.cert_storage_mode,
            hostname_count=global_counts["hostnames"],
            cert_count=global_counts["certificates"],
            obs_count=global_counts["observations"],
            cert_hostname_count=global_counts["cert_hostnames"],
            backfill_days=active_settings.backfill_days,
            cert_retention_days=active_settings.cert_retention_days,
            observation_retention_days=active_settings.observation_retention_days,
            entry_outcome_retention_days=active_settings.entry_outcome_retention_days,
        )
    except Exception:
        _logger.warning("Profile projection failed; falling back to linear")
        return None


def build_projection_dict(
    *,
    global_counts: dict[str, int],
    database_size_bytes: int,
    backfill_progress: dict[str, int],
    active_settings: Any,
    ct_log_progress: dict[str, int] | None = None,
) -> dict[str, Any]:
    """Build the storage_projection sub-dict for the stats payload.

    Falls back to CT log tree-size totals when no backfill plan exists,
    allowing a meaningful projection on fresh installs and lite-mode
    deployments where backfill has never been run.

    Args:
        global_counts: Output of query_global_counts.
        database_size_bytes: Total DB size in bytes.
        backfill_progress: Output of query_backfill_planned_counts.
        active_settings: Active CtInstanceSettings row or None.
        ct_log_progress: Output of query_ct_log_progress_totals or None.
    """
    try:
        from ctpool.profile_projection import compute_projection_confidence
    except ImportError:
        _logger.warning("profile_projection unavailable; projection omitted")
        return {"status": "insufficient_backfill_plan", "notes": []}

    planned_total, planned_completed, projection_basis = _resolve_effective_progress(
        backfill_progress, ct_log_progress
    )
    obs_count = global_counts["observations"]
    base = _build_projection_base(
        global_counts, database_size_bytes, planned_total, planned_completed
    )

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
                "Storage projection unavailable. "
                "No backfill plan and no CT log tree sizes available."
            ],
        }

    confidence = compute_projection_confidence(max(obs_count, 1))
    profile_result = _try_profile_projection(global_counts, active_settings)

    return _build_available_projection(
        base=base,
        database_size_bytes=database_size_bytes,
        obs_count=obs_count,
        planned_total=planned_total,
        planned_completed=planned_completed,
        confidence=confidence,
        projection_basis=projection_basis,
        profile_result=profile_result,
    )
