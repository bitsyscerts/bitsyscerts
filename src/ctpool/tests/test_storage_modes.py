"""Unit tests for ctpool.storage_modes and ctpool.profile_projection.

Covers:
    - CertStorageMode and StorageProfile enum values
    - flags_for_mode: correct flags per mode
    - resolve_profile_defaults: profile→mode mapping + override
    - bytes_per_observation_range: returns non-zero tuple
    - project_storage: calculation is consistent with range
"""

from __future__ import annotations

import pytest

from ctpool.profile_projection import bytes_per_observation_range, project_storage
from ctpool.storage_modes import (
    CertStorageMode,
    StorageProfile,
    flags_for_mode,
    resolve_profile_defaults,
)

# ---------------------------------------------------------------------------
# CertStorageMode enum
# ---------------------------------------------------------------------------


def test_cert_storage_mode_values():
    assert CertStorageMode.NONE == "none"
    assert CertStorageMode.METADATA == "metadata"
    assert CertStorageMode.METADATA_SPKI == "metadata_spki"
    assert CertStorageMode.METADATA_PUBLIC_KEY == "metadata_public_key"
    assert CertStorageMode.FULL_DER == "full_der"


# ---------------------------------------------------------------------------
# StorageProfile enum
# ---------------------------------------------------------------------------


def test_storage_profile_values():
    assert StorageProfile.LITE == "lite"
    assert StorageProfile.ARCHIVE == "archive"
    assert StorageProfile.CUSTOM == "custom"


# ---------------------------------------------------------------------------
# flags_for_mode
# ---------------------------------------------------------------------------


def test_flags_none_mode():
    flags = flags_for_mode(CertStorageMode.NONE)
    assert flags.skip_cert is True
    assert flags.include_public_key_der is False
    assert flags.include_raw_der is False


def test_flags_metadata_mode():
    flags = flags_for_mode(CertStorageMode.METADATA)
    assert flags.skip_cert is False
    assert flags.include_public_key_der is False
    assert flags.include_raw_der is False


def test_flags_metadata_spki_same_as_metadata():
    assert flags_for_mode(CertStorageMode.METADATA_SPKI) == flags_for_mode(
        CertStorageMode.METADATA
    )


def test_flags_metadata_public_key():
    flags = flags_for_mode(CertStorageMode.METADATA_PUBLIC_KEY)
    assert flags.skip_cert is False
    assert flags.include_public_key_der is True
    assert flags.include_raw_der is False


def test_flags_full_der():
    flags = flags_for_mode(CertStorageMode.FULL_DER)
    assert flags.skip_cert is False
    assert flags.include_public_key_der is True
    assert flags.include_raw_der is True


# ---------------------------------------------------------------------------
# resolve_profile_defaults
# ---------------------------------------------------------------------------


def test_resolve_lite_profile_default():
    profile, mode = resolve_profile_defaults("lite")
    assert profile == StorageProfile.LITE
    # Changed from NONE to METADATA: cert metadata is product data;
    # NONE skipped all Certificate rows which broke the Certificates page.
    assert mode == CertStorageMode.METADATA


def test_resolve_standard_profile_default():
    profile, mode = resolve_profile_defaults("standard")
    assert mode == CertStorageMode.METADATA


def test_resolve_archive_profile_default():
    profile, mode = resolve_profile_defaults("archive")
    assert mode == CertStorageMode.FULL_DER


def test_resolve_profile_with_override():
    profile, mode = resolve_profile_defaults(
        "lite", cert_storage_mode_override="metadata"
    )
    assert profile == StorageProfile.LITE
    assert mode == CertStorageMode.METADATA


def test_resolve_invalid_profile_raises():
    with pytest.raises(ValueError):
        resolve_profile_defaults("nonexistent")


def test_resolve_invalid_mode_override_raises():
    with pytest.raises(ValueError):
        resolve_profile_defaults("lite", cert_storage_mode_override="invalid_mode")


# ---------------------------------------------------------------------------
# bytes_per_observation_range
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("mode", list(CertStorageMode))
def test_bytes_per_observation_range_all_modes(mode):
    low, high = bytes_per_observation_range(mode)
    assert low > 0
    assert high >= low


def test_none_mode_bytes_lowest():
    low_none, _ = bytes_per_observation_range(CertStorageMode.NONE)
    low_meta, _ = bytes_per_observation_range(CertStorageMode.METADATA)
    assert low_none < low_meta


def test_full_der_bytes_highest():
    _, high_meta = bytes_per_observation_range(CertStorageMode.METADATA)
    _, high_full = bytes_per_observation_range(CertStorageMode.FULL_DER)
    assert high_full > high_meta


# ---------------------------------------------------------------------------
# project_storage
# ---------------------------------------------------------------------------


def test_project_storage_zero_observations():
    result = project_storage(0, CertStorageMode.METADATA)
    assert result.bytes_low == 0
    assert result.bytes_high == 0
    assert result.gb_low == pytest.approx(0.0)


def test_project_storage_consistent_with_range():
    obs = 1_000_000
    result = project_storage(obs, CertStorageMode.METADATA)
    low, high = bytes_per_observation_range(CertStorageMode.METADATA)
    assert result.bytes_low == obs * low
    assert result.bytes_high == obs * high


def test_project_storage_gb_computation():
    result = project_storage(1_073_741_824, CertStorageMode.NONE)
    low, _ = bytes_per_observation_range(CertStorageMode.NONE)
    assert result.gb_low == pytest.approx(float(low))
