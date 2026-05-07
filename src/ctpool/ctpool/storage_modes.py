"""Storage mode and profile definitions for BitsysCerts.

Exports:
    CertStorageMode          — Enum of certificate storage granularities.
    StorageProfile           — Enum of named storage profiles.
    CertificatePersistenceFlags — Resolved write-path flags for one ingestion.
    flags_for_mode           — Derive CertificatePersistenceFlags from a mode.
    resolve_profile_defaults — Return (StorageProfile, CertStorageMode) for a
                               profile name, applying archive guard.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class CertStorageMode(StrEnum):
    """Controls which certificate data is persisted per CT entry.

    Modes from least to most storage:

    NONE             — Hostnames and observations only; no Certificate rows.
    METADATA         — Certificate metadata fields; no binary blobs.
    METADATA_SPKI    — Certificate metadata; semantically identical to METADATA
                       in the current schema (spki_sha256 is always stored).
    METADATA_PUBLIC_KEY — Metadata + ``public_key_der`` BYTEA column.
    FULL_DER         — Metadata + ``public_key_der`` + ``raw_der`` BYTEA.
    """

    NONE = "none"
    METADATA = "metadata"
    METADATA_SPKI = "metadata_spki"
    METADATA_PUBLIC_KEY = "metadata_public_key"
    FULL_DER = "full_der"


class StorageProfile(StrEnum):
    """Named storage profiles.

    Profiles are opinionated bundles of retention defaults.
    The ``custom`` profile defers all decisions to individual
    ``CT_*`` environment variables.
    """

    LITE = "lite"
    STANDARD = "standard"
    RESEARCH = "research"
    ARCHIVE = "archive"
    CUSTOM = "custom"


@dataclass(frozen=True)
class CertificatePersistenceFlags:
    """Resolved write-path flags for one CT entry ingestion.

    Derived from CertStorageMode at startup; consulted by cert_writer.py
    and writer.py for every entry written.
    """

    skip_cert: bool
    """If True, skip all Certificate / CertificateHostname upserts."""
    include_public_key_der: bool
    """If True, persist the public_key_der BYTEA column."""
    include_raw_der: bool
    """If True, persist the raw_der BYTEA column."""


# Pre-computed flag table for each mode.
_FLAGS: dict[CertStorageMode, CertificatePersistenceFlags] = {
    CertStorageMode.NONE: CertificatePersistenceFlags(
        skip_cert=True, include_public_key_der=False, include_raw_der=False
    ),
    CertStorageMode.METADATA: CertificatePersistenceFlags(
        skip_cert=False, include_public_key_der=False, include_raw_der=False
    ),
    CertStorageMode.METADATA_SPKI: CertificatePersistenceFlags(
        skip_cert=False, include_public_key_der=False, include_raw_der=False
    ),
    CertStorageMode.METADATA_PUBLIC_KEY: CertificatePersistenceFlags(
        skip_cert=False, include_public_key_der=True, include_raw_der=False
    ),
    CertStorageMode.FULL_DER: CertificatePersistenceFlags(
        skip_cert=False, include_public_key_der=True, include_raw_der=True
    ),
}

# Default cert_storage_mode per profile.
_PROFILE_CERT_MODE: dict[StorageProfile, CertStorageMode] = {
    StorageProfile.LITE: CertStorageMode.NONE,
    StorageProfile.STANDARD: CertStorageMode.METADATA,
    StorageProfile.RESEARCH: CertStorageMode.METADATA,
    StorageProfile.ARCHIVE: CertStorageMode.FULL_DER,
    StorageProfile.CUSTOM: CertStorageMode.NONE,
}


def flags_for_mode(mode: CertStorageMode) -> CertificatePersistenceFlags:
    """Return CertificatePersistenceFlags for the given CertStorageMode.

    Args:
        mode: The certificate storage mode to resolve.

    Returns:
        Immutable flags struct consumed by the write pipeline.
    """
    return _FLAGS[mode]


def resolve_profile_defaults(
    profile_name: str,
    cert_storage_mode_override: str | None = None,
) -> tuple[StorageProfile, CertStorageMode]:
    """Return the resolved (StorageProfile, CertStorageMode) pair.

    If ``cert_storage_mode_override`` is provided it takes precedence over
    the profile default.

    Args:
        profile_name:              Value of CT_STORAGE_PROFILE.
        cert_storage_mode_override: Optional CT_CERT_STORAGE_MODE override.

    Returns:
        A (StorageProfile, CertStorageMode) tuple.
    """
    profile = StorageProfile(profile_name)
    if cert_storage_mode_override:
        cert_mode = CertStorageMode(cert_storage_mode_override)
    else:
        cert_mode = _PROFILE_CERT_MODE[profile]
    return profile, cert_mode
