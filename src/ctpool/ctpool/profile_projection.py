"""Per-mode storage capacity projections for the storage profile API.

Exports:
    bytes_per_observation_range — (low, high) bytes per observation for a mode.
    project_storage             — Compute low/high byte estimates for a given
                                  observation count and cert storage mode.
"""

from __future__ import annotations

from dataclasses import dataclass

from ctpool.storage_modes import CertStorageMode

# Bytes-per-observation estimates (empirically derived; see AGENTS.md T9 section).
_BYTES_PER_OBS: dict[CertStorageMode, tuple[int, int]] = {
    CertStorageMode.NONE: (120, 200),
    CertStorageMode.METADATA: (500, 800),
    CertStorageMode.METADATA_SPKI: (500, 800),
    CertStorageMode.METADATA_PUBLIC_KEY: (900, 1400),
    CertStorageMode.FULL_DER: (2000, 3500),
}


@dataclass(frozen=True)
class StorageProjectionResult:
    """Low/high byte estimates for a given observation count and cert mode."""

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

    Args:
        mode: The certificate storage mode to project.

    Returns:
        A (low_bytes, high_bytes) tuple.
    """
    return _BYTES_PER_OBS[mode]


def project_storage(
    observation_count: int,
    cert_storage_mode: CertStorageMode,
) -> StorageProjectionResult:
    """Compute low/high storage byte estimates.

    Args:
        observation_count:  Total number of CT log observation rows.
        cert_storage_mode:  Active certificate storage mode.

    Returns:
        A StorageProjectionResult with byte and GB estimates.
    """
    low, high = _BYTES_PER_OBS[cert_storage_mode]
    return StorageProjectionResult(
        cert_storage_mode=cert_storage_mode.value,
        observation_count=observation_count,
        bytes_low=observation_count * low,
        bytes_high=observation_count * high,
    )
