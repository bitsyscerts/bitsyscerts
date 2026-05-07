"""Unit tests for ctpool.profile_defaults."""

from __future__ import annotations

from ctpool.profile_defaults import PROFILE_DEFAULTS, defaults_for_profile
from ctpool.storage_modes import StorageProfile


def test_all_profiles_have_defaults() -> None:
    """Every StorageProfile value has an entry in PROFILE_DEFAULTS."""
    for profile in StorageProfile:
        assert profile in PROFILE_DEFAULTS


def test_defaults_for_profile_returns_copy() -> None:
    """defaults_for_profile returns a new dict each call (not the same object)."""
    a = defaults_for_profile(StorageProfile.LITE)
    b = defaults_for_profile(StorageProfile.LITE)
    assert a is not b


def test_lite_defaults() -> None:
    """Lite profile defaults to none cert mode and 30-day backfill."""
    d = defaults_for_profile(StorageProfile.LITE)
    assert d["storage_profile"] == "lite"
    assert d["cert_storage_mode"] == "none"
    assert d["hostname_retention_mode"] == "forever"
    assert d["backfill_days"] == 30
    assert d["cert_retention_days"] == 1
    assert d["observation_retention_days"] == 7
    assert d["entry_outcome_retention_days"] == 7
    assert d["metrics_retention_days"] == 14


def test_standard_defaults() -> None:
    """Standard profile defaults to metadata_spki and 90-day retention."""
    d = defaults_for_profile(StorageProfile.STANDARD)
    assert d["storage_profile"] == "standard"
    assert d["cert_storage_mode"] == "metadata_spki"
    assert d["backfill_days"] == 90
    assert d["cert_retention_days"] == 90


def test_research_defaults() -> None:
    """Research profile defaults to metadata_public_key and 180-day retention."""
    d = defaults_for_profile(StorageProfile.RESEARCH)
    assert d["storage_profile"] == "research"
    assert d["cert_storage_mode"] == "metadata_public_key"
    assert d["backfill_days"] == 180
    assert d["cert_retention_days"] == 180


def test_archive_defaults_full_der_zero_retention() -> None:
    """Archive profile uses full_der and 0-day retention (retain indefinitely)."""
    d = defaults_for_profile(StorageProfile.ARCHIVE)
    assert d["storage_profile"] == "archive"
    assert d["cert_storage_mode"] == "full_der"
    assert d["backfill_days"] == 0
    assert d["cert_retention_days"] == 0
    assert d["observation_retention_days"] == 0
    assert d["entry_outcome_retention_days"] == 0
    assert d["metrics_retention_days"] == 90


def test_custom_defaults() -> None:
    """Custom profile uses safe defaults mirroring Lite."""
    d = defaults_for_profile(StorageProfile.CUSTOM)
    assert d["storage_profile"] == "custom"
    assert d["cert_storage_mode"] == "none"


def test_defaults_for_profile_all_required_keys_present() -> None:
    """Each profile dict contains all 8 required field keys."""
    required = {
        "storage_profile",
        "cert_storage_mode",
        "hostname_retention_mode",
        "backfill_days",
        "cert_retention_days",
        "observation_retention_days",
        "entry_outcome_retention_days",
        "metrics_retention_days",
    }
    for profile in StorageProfile:
        d = defaults_for_profile(profile)
        assert required <= set(d.keys()), f"Profile {profile} missing keys"
