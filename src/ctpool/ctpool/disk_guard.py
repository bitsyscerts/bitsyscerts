"""Disk space safety guard.

Provides threshold checks so workers can pause or abort before filling the
volume that hosts the PostgreSQL data directory.
"""

from __future__ import annotations

import shutil

from ctpool.exceptions import DiskGuardError


def get_free_disk_gb(path: str = "/") -> float:
    """Return free disk space in GiB for the volume containing *path*.

    Args:
        path: Filesystem path to check. Defaults to the root volume.

    Returns:
        Free disk space in gibibytes (GiB).

    Raises:
        DiskGuardError: If the path does not exist or is not accessible.
    """
    try:
        usage = shutil.disk_usage(path)
    except (FileNotFoundError, PermissionError, OSError) as exc:
        raise DiskGuardError(
            f"Cannot check disk usage for path {path!r}: {exc}"
        ) from exc
    return usage.free / (1024**3)


def is_disk_low(min_free_gb: int) -> bool:
    """Return True when free disk space is below *min_free_gb*.

    Args:
        min_free_gb: Low-water threshold in GiB (from Settings.ct_min_free_disk_gb).
    """
    return get_free_disk_gb() < min_free_gb


def is_disk_critical(critical_free_gb: int) -> bool:
    """Return True when free disk space is below *critical_free_gb*.

    Args:
        critical_free_gb: Critical threshold in GiB
            (from Settings.ct_critical_free_disk_gb).
    """
    return get_free_disk_gb() < critical_free_gb
