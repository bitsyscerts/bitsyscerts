"""Unit tests for storage projection math."""

from __future__ import annotations

import pytest

from certsapi.stats.projection import (
    DiskSnapshot,
    ProjectionInputs,
    compute_storage_projection,
)


def _inputs(**overrides: int) -> ProjectionInputs:
    defaults = {
        "database_size_bytes": 10_000,
        "ct_observations_count": 100,
        "certificates_count": 50,
        "hostnames_count": 80,
        "certificate_hostnames_count": 120,
        "planned_observations_total": 1_000,
        "planned_observations_completed": 250,
    }
    defaults.update(overrides)
    return ProjectionInputs(**defaults)


def test_projection_unavailable_when_observations_missing() -> None:
    projection = compute_storage_projection(_inputs(ct_observations_count=0))
    assert projection.status == "insufficient_observations"
    assert projection.bytes_per_observation_current is None


def test_projection_unavailable_when_no_backfill_plan() -> None:
    projection = compute_storage_projection(_inputs(planned_observations_total=0))
    assert projection.status == "insufficient_backfill_plan"
    assert projection.sync_percent_by_observation is None


def test_projection_math_uses_current_density() -> None:
    projection = compute_storage_projection(_inputs())
    assert projection.bytes_per_observation_current == pytest.approx(100.0)
    assert projection.planned_observations_remaining == 750
    assert projection.projected_remaining_database_size_bytes == 75_000
    assert projection.projected_final_database_size_bytes == 85_000
    assert projection.storage_percent_of_projected == pytest.approx(10_000 / 85_000)
    assert projection.sync_percent_by_observation == pytest.approx(0.25)


def test_projection_clamps_completed_to_total() -> None:
    projection = compute_storage_projection(
        _inputs(planned_observations_completed=2_000),
    )
    assert projection.planned_observations_completed == 1_000
    assert projection.planned_observations_remaining == 0
    assert projection.sync_percent_by_observation == pytest.approx(1.0)


def test_projection_marks_disk_fit_true_when_headroom_remains() -> None:
    projection = compute_storage_projection(
        _inputs(),
        disk_snapshot=DiskSnapshot(
            total_bytes=200_000,
            used_bytes=20_000,
            free_bytes=180_000,
            min_free_bytes=50_000,
        ),
    )
    assert projection.projected_disk_free_after_sync_bytes == 105_000
    assert projection.projected_fits_on_disk is True


def test_projection_marks_disk_fit_false_when_below_minimum_free() -> None:
    projection = compute_storage_projection(
        _inputs(),
        disk_snapshot=DiskSnapshot(
            total_bytes=120_000,
            used_bytes=20_000,
            free_bytes=100_000,
            min_free_bytes=30_000,
        ),
    )
    assert projection.projected_fits_on_disk is False
    assert any("configured minimum free disk" in note for note in projection.notes)
