"""Unit tests for ctpool.profile_projection."""

from __future__ import annotations

from ctpool.profile_projection import (
    ProfileAwareProjectionResult,
    bytes_per_observation_range,
    compute_profile_aware_projection,
    project_storage,
)
from ctpool.storage_modes import CertStorageMode, StorageProfile


def test_lite_projection_far_smaller_than_archive() -> None:
    """Lite mode estimate must be < 1/10 of archive mode for same inputs."""
    shared = {
        "hostname_count": 100_000,
        "cert_count": 50_000,
        "obs_count": 500_000,
        "cert_hostname_count": 200_000,
        "backfill_days": 30,
    }
    lite = compute_profile_aware_projection(
        profile=StorageProfile.LITE,
        cert_storage_mode=CertStorageMode.NONE,
        cert_retention_days=1,
        observation_retention_days=7,
        entry_outcome_retention_days=7,
        **shared,
    )
    archive = compute_profile_aware_projection(
        profile=StorageProfile.ARCHIVE,
        cert_storage_mode=CertStorageMode.FULL_DER,
        cert_retention_days=0,
        observation_retention_days=0,
        entry_outcome_retention_days=0,
        **shared,
    )
    assert archive.projected_total_bytes > lite.projected_total_bytes * 10


def test_cert_mode_none_zero_cert_bytes() -> None:
    """cert_storage_mode=none must produce zero certificate metadata bytes."""
    result = compute_profile_aware_projection(
        profile=StorageProfile.LITE,
        cert_storage_mode=CertStorageMode.NONE,
        hostname_count=0,
        cert_count=0,
        obs_count=0,
        cert_hostname_count=0,
        backfill_days=30,
        cert_retention_days=1,
        observation_retention_days=7,
        entry_outcome_retention_days=7,
    )
    assert result.certificate_metadata_bytes == 0
    assert result.certificate_public_key_bytes == 0
    assert result.raw_cert_der_bytes == 0


def test_full_der_mode_includes_raw_bytes() -> None:
    """full_der mode must produce non-zero raw_cert_der_bytes."""
    result = compute_profile_aware_projection(
        profile=StorageProfile.RESEARCH,
        cert_storage_mode=CertStorageMode.FULL_DER,
        hostname_count=0,
        cert_count=10_000,
        obs_count=0,
        cert_hostname_count=0,
        backfill_days=180,
        cert_retention_days=180,
        observation_retention_days=180,
        entry_outcome_retention_days=180,
    )
    assert result.raw_cert_der_bytes > 0


def test_projection_result_returns_correct_profile_value() -> None:
    """profile field in result matches the input StorageProfile."""
    result = compute_profile_aware_projection(
        profile=StorageProfile.STANDARD,
        cert_storage_mode=CertStorageMode.METADATA_SPKI,
        hostname_count=0,
        cert_count=0,
        obs_count=0,
        cert_hostname_count=0,
        backfill_days=90,
        cert_retention_days=90,
        observation_retention_days=90,
        entry_outcome_retention_days=90,
    )
    assert result.profile == "standard"
    assert result.cert_storage_mode == "metadata_spki"


def test_notes_are_populated() -> None:
    """Notes list must contain at least one entry for any profile."""
    result = compute_profile_aware_projection(
        profile=StorageProfile.LITE,
        cert_storage_mode=CertStorageMode.NONE,
        hostname_count=0,
        cert_count=0,
        obs_count=0,
        cert_hostname_count=0,
        backfill_days=30,
        cert_retention_days=1,
        observation_retention_days=7,
        entry_outcome_retention_days=7,
    )
    assert len(result.notes) > 0


def test_string_inputs_accepted() -> None:
    """profile and cert_storage_mode can be provided as plain strings."""
    result = compute_profile_aware_projection(
        profile="lite",
        cert_storage_mode="none",
        hostname_count=0,
        cert_count=0,
        obs_count=0,
        cert_hostname_count=0,
        backfill_days=30,
        cert_retention_days=1,
        observation_retention_days=7,
        entry_outcome_retention_days=7,
    )
    assert isinstance(result, ProfileAwareProjectionResult)


def test_total_is_sum_of_parts_plus_index() -> None:
    """projected_total_bytes must equal sum of all category bytes + overhead."""
    r = compute_profile_aware_projection(
        profile=StorageProfile.STANDARD,
        cert_storage_mode=CertStorageMode.METADATA_SPKI,
        hostname_count=100_000,
        cert_count=50_000,
        obs_count=500_000,
        cert_hostname_count=200_000,
        backfill_days=90,
        cert_retention_days=90,
        observation_retention_days=90,
        entry_outcome_retention_days=90,
    )
    expected = (
        r.hostname_index_bytes
        + r.certificate_metadata_bytes
        + r.certificate_public_key_bytes
        + r.raw_cert_der_bytes
        + r.ct_observations_bytes
        + r.entry_outcomes_bytes
        + r.cert_hostname_relationships_bytes
        + r.metrics_and_ops_bytes
        + r.index_overhead_bytes
    )
    assert r.projected_total_bytes == expected


# --- Legacy shim tests -------------------------------------------------------


def test_bytes_per_observation_range_none_mode() -> None:
    """Legacy shim returns expected (120, 200) for none mode."""
    low, high = bytes_per_observation_range(CertStorageMode.NONE)
    assert low == 120
    assert high == 200


def test_project_storage_legacy_math() -> None:
    """Legacy project_storage multiplies count × per-obs bytes."""
    result = project_storage(1_000, CertStorageMode.NONE)
    assert result.bytes_low == 1_000 * 120
    assert result.bytes_high == 1_000 * 200
    assert result.gb_low < result.gb_high


def test_project_storage_positive_gb_values() -> None:
    """gb_low and gb_high must be positive for non-zero observation count."""
    result = project_storage(1_000_000, CertStorageMode.METADATA_SPKI)
    assert result.gb_low > 0
    assert result.gb_high > result.gb_low
