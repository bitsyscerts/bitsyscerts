"""Default field values for each named storage profile.

Exports:
    PROFILE_DEFAULTS — dict mapping StorageProfile → frozen default dict.
    defaults_for_profile — Return the default field dict for *profile*.
"""

from __future__ import annotations

from ctpool.storage_modes import StorageProfile

# Each inner dict contains exactly the fields stored in ct_instance_settings
# (excluding id, created_at, updated_at, updated_by, settings_hash, settings_json).
PROFILE_DEFAULTS: dict[StorageProfile, dict[str, object]] = {
    StorageProfile.LITE: {
        "storage_profile": "lite",
        "cert_storage_mode": "none",
        "hostname_retention_mode": "forever",
        "backfill_days": 30,
        "cert_retention_days": 1,
        "observation_retention_days": 7,
        "entry_outcome_retention_days": 7,
        "metrics_retention_days": 14,
    },
    StorageProfile.STANDARD: {
        "storage_profile": "standard",
        "cert_storage_mode": "metadata_spki",
        "hostname_retention_mode": "forever",
        "backfill_days": 90,
        "cert_retention_days": 90,
        "observation_retention_days": 30,
        "entry_outcome_retention_days": 30,
        "metrics_retention_days": 30,
    },
    StorageProfile.RESEARCH: {
        "storage_profile": "research",
        "cert_storage_mode": "metadata_public_key",
        "hostname_retention_mode": "forever",
        "backfill_days": 180,
        "cert_retention_days": 180,
        "observation_retention_days": 180,
        "entry_outcome_retention_days": 180,
        "metrics_retention_days": 60,
    },
    StorageProfile.ARCHIVE: {
        "storage_profile": "archive",
        "cert_storage_mode": "full_der",
        "hostname_retention_mode": "forever",
        "backfill_days": 0,
        "cert_retention_days": 0,
        "observation_retention_days": 0,
        "entry_outcome_retention_days": 0,
        "metrics_retention_days": 90,
    },
    StorageProfile.CUSTOM: {
        "storage_profile": "custom",
        "cert_storage_mode": "none",
        "hostname_retention_mode": "forever",
        "backfill_days": 30,
        "cert_retention_days": 7,
        "observation_retention_days": 7,
        "entry_outcome_retention_days": 7,
        "metrics_retention_days": 14,
    },
}


def defaults_for_profile(profile: StorageProfile) -> dict[str, object]:
    """Return a copy of the default field dict for *profile*.

    Args:
        profile: The named storage profile.

    Returns:
        A shallow copy of the defaults dict for the profile.

    Raises:
        KeyError: If *profile* is not in PROFILE_DEFAULTS (should not happen
            for valid StorageProfile enum values).
    """
    return dict(PROFILE_DEFAULTS[profile])
