"""Per-profile storage capacity projections.

# NOTE (201-500 line warning zone): this module consolidates projection math
# (per-category estimates) and two legacy shims in one place. Splitting the
# shims to a separate file would scatter closely related projection logic
# across two modules with no cohesion benefit. Resolve by removing the shims
# once cli_storage_commands is updated to use the new API directly.

Exports:
    ProfileAwareProjectionResult — dataclass with per-category byte estimates.
    compute_profile_aware_projection — Profile-driven projection formula.
    bytes_per_observation_range — Legacy shim kept for backward compat.
    project_storage — Legacy shim kept for backward compat.
    StorageProjectionResult — Legacy result dataclass.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ctpool.storage_modes import CertStorageMode, StorageProfile

# ---------------------------------------------------------------------------
# Per-category byte estimates (empirically derived, per-row basis)
# ---------------------------------------------------------------------------

_BYTES_PER_HOSTNAME = 200
_BYTES_PER_HOSTNAME_CERT_SUMMARY = 150
_BYTES_PER_CERT_METADATA = 600
_BYTES_PER_PUBLIC_KEY_DER = 300
_BYTES_PER_RAW_DER = 1_800
_BYTES_PER_OBSERVATION = 150
_BYTES_PER_ENTRY_OUTCOME = 250
_BYTES_PER_CERT_HOSTNAME_JOIN = 120
_BYTES_PER_METRICS_OPS = 80
_INDEX_OVERHEAD_FACTOR = 1.35

# Estimated daily new CT entries across all monitored logs
_DAILY_CT_ENTRIES_ESTIMATE = 4_000_000

# Legacy per-observation mapping
_LEGACY_BYTES_PER_OBS: dict[CertStorageMode, tuple[int, int]] = {
    CertStorageMode.NONE: (120, 200),
    CertStorageMode.METADATA: (500, 800),
    CertStorageMode.METADATA_SPKI: (500, 800),
    CertStorageMode.METADATA_PUBLIC_KEY: (900, 1400),
    CertStorageMode.FULL_DER: (2000, 3500),
}


@dataclass(frozen=True)
class ProfileAwareProjectionResult:
    """Profile-driven storage size estimate broken down by category."""

    profile: str
    cert_storage_mode: str
    hostname_index_bytes: int
    certificate_metadata_bytes: int
    certificate_public_key_bytes: int
    raw_cert_der_bytes: int
    ct_observations_bytes: int
    entry_outcomes_bytes: int
    cert_hostname_relationships_bytes: int
    metrics_and_ops_bytes: int
    index_overhead_bytes: int
    projected_total_bytes: int
    notes: list[str] = field(default_factory=list)

    @property
    def projected_total_gb(self) -> float:
        """Projected total in GiB."""
        return self.projected_total_bytes / 1_073_741_824


def _retention_multiplier(retention_days: int) -> float:
    """Convert retention days to a daily-rate multiplier.

    Zero means indefinite; use a 5-year horizon for archive mode.
    """
    if retention_days <= 0:
        return 365 * 5
    return float(retention_days)


def _compute_category_bytes(
    mode: CertStorageMode,
    hostname_count: int,
    cert_count: int,
    obs_count: int,
    cert_hostname_count: int,
    cert_retention_mult: float,
    obs_retention_mult: float,
    outcome_retention_mult: float,
) -> tuple[int, int, int, int, int, int, int, int]:
    """Return per-category byte estimates as an 8-tuple.

    Returns (hostname, cert_meta, cert_pubkey, cert_raw_der, obs,
             outcome, cert_hostname, metrics).
    """
    daily = _DAILY_CT_ENTRIES_ESTIMATE
    projected_obs = max(obs_count, int(daily * obs_retention_mult))
    projected_certs = max(cert_count, int(daily * 0.05 * cert_retention_mult))
    projected_outcomes = max(obs_count, int(daily * outcome_retention_mult))

    hostname_bytes = int(
        max(hostname_count, 1_000_000)
        * (_BYTES_PER_HOSTNAME + _BYTES_PER_HOSTNAME_CERT_SUMMARY)
    )
    cert_meta = 0
    cert_pubkey = 0
    cert_raw = 0
    if mode != CertStorageMode.NONE:
        cert_meta = int(projected_certs * _BYTES_PER_CERT_METADATA)
    if mode in (CertStorageMode.METADATA_PUBLIC_KEY, CertStorageMode.FULL_DER):
        cert_pubkey = int(projected_certs * _BYTES_PER_PUBLIC_KEY_DER)
    if mode == CertStorageMode.FULL_DER:
        cert_raw = int(projected_certs * _BYTES_PER_RAW_DER)

    obs_bytes = int(projected_obs * _BYTES_PER_OBSERVATION)
    outcome_bytes = int(projected_outcomes * _BYTES_PER_ENTRY_OUTCOME)
    ch_bytes = 0
    if mode != CertStorageMode.NONE:
        ch_bytes = int(
            max(cert_hostname_count, projected_certs * 2)
            * _BYTES_PER_CERT_HOSTNAME_JOIN
        )
    metrics_bytes = int(projected_obs * _BYTES_PER_METRICS_OPS)
    return (
        hostname_bytes,
        cert_meta,
        cert_pubkey,
        cert_raw,
        obs_bytes,
        outcome_bytes,
        ch_bytes,
        metrics_bytes,
    )


def compute_profile_aware_projection(
    profile: StorageProfile | str,
    cert_storage_mode: CertStorageMode | str,
    hostname_count: int,
    cert_count: int,
    obs_count: int,
    cert_hostname_count: int,
    backfill_days: int,
    cert_retention_days: int,
    observation_retention_days: int,
    entry_outcome_retention_days: int,
) -> ProfileAwareProjectionResult:
    """Compute a profile-aware storage projection from current row counts.

    Uses per-category byte estimates scaled by active retention windows rather
    than extrapolating from total planned CT log observations.  This prevents
    Lite mode from producing Archive-style 25+ TB projections.
    """
    mode = (
        CertStorageMode(cert_storage_mode)
        if isinstance(cert_storage_mode, str)
        else cert_storage_mode
    )
    profile_val = StorageProfile(profile) if isinstance(profile, str) else profile
    cert_mult = _retention_multiplier(cert_retention_days)
    obs_mult = _retention_multiplier(observation_retention_days)
    outcome_mult = _retention_multiplier(entry_outcome_retention_days)

    (
        hostname_bytes,
        cert_meta,
        cert_pubkey,
        cert_raw,
        obs_bytes,
        outcome_bytes,
        ch_bytes,
        metrics_bytes,
    ) = _compute_category_bytes(
        mode,
        hostname_count,
        cert_count,
        obs_count,
        cert_hostname_count,
        cert_mult,
        obs_mult,
        outcome_mult,
    )
    subtotal = (
        hostname_bytes
        + cert_meta
        + cert_pubkey
        + cert_raw
        + obs_bytes
        + outcome_bytes
        + ch_bytes
        + metrics_bytes
    )
    index_bytes = int(subtotal * (_INDEX_OVERHEAD_FACTOR - 1.0))
    total_bytes = subtotal + index_bytes

    notes = _build_notes(profile_val, mode, backfill_days, observation_retention_days)
    return ProfileAwareProjectionResult(
        profile=profile_val.value,
        cert_storage_mode=mode.value,
        hostname_index_bytes=hostname_bytes,
        certificate_metadata_bytes=cert_meta,
        certificate_public_key_bytes=cert_pubkey,
        raw_cert_der_bytes=cert_raw,
        ct_observations_bytes=obs_bytes,
        entry_outcomes_bytes=outcome_bytes,
        cert_hostname_relationships_bytes=ch_bytes,
        metrics_and_ops_bytes=metrics_bytes,
        index_overhead_bytes=index_bytes,
        projected_total_bytes=total_bytes,
        notes=notes,
    )


def _build_notes(
    profile: StorageProfile,
    mode: CertStorageMode,
    backfill_days: int,
    observation_retention_days: int,
) -> list[str]:
    """Return human-readable notes describing the projection basis."""
    notes: list[str] = [
        "Projection uses per-category byte averages scaled by retention windows."
    ]
    if profile == StorageProfile.ARCHIVE:
        notes.append(
            "Archive mode retains full certificate history. "
            "Indefinite categories use a 5-year horizon."
        )
    if profile == StorageProfile.LITE:
        notes.append("Lite mode: only hostname index and latest cert summaries stored.")
    if mode == CertStorageMode.NONE:
        notes.append("cert_storage_mode=none: certificate rows excluded.")
    if backfill_days == 0:
        notes.append("backfill_days=0: full CT log history ingestion (archive mode).")
    if observation_retention_days == 0:
        notes.append("observation_retention_days=0: indefinite. Uses 5-year horizon.")
    return notes


# ---------------------------------------------------------------------------
# Legacy shims — kept for cli_storage_commands backward compatibility
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class StorageProjectionResult:
    """Legacy per-observation projection result."""

    cert_storage_mode: str
    observation_count: int
    bytes_low: int
    bytes_high: int

    @property
    def gb_low(self) -> float:
        """Low estimate in gigabytes."""
        return self.bytes_low / 1_073_741_824

    @property
    def gb_high(self) -> float:
        """High estimate in gigabytes."""
        return self.bytes_high / 1_073_741_824


def bytes_per_observation_range(mode: CertStorageMode) -> tuple[int, int]:
    """Return (low, high) bytes per observation for *mode*.

    .. deprecated:: Use compute_profile_aware_projection() for new code.
    """
    return _LEGACY_BYTES_PER_OBS[mode]


def project_storage(
    observation_count: int,
    cert_storage_mode: CertStorageMode,
) -> StorageProjectionResult:
    """Legacy per-observation projection.

    .. deprecated:: Use compute_profile_aware_projection() for new code.
    """
    low, high = _LEGACY_BYTES_PER_OBS[cert_storage_mode]
    return StorageProjectionResult(
        cert_storage_mode=cert_storage_mode.value,
        observation_count=observation_count,
        bytes_low=observation_count * low,
        bytes_high=observation_count * high,
    )
