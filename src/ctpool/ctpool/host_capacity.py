"""Collects host-level resource metrics via psutil.

Exports:
    collect_host_capacity — returns a plain dict with CPU, memory, disk,
        and I/O counters.  All fields default to ``None`` when the
        underlying psutil call is unavailable or raises an error.
"""

from __future__ import annotations

import logging
from typing import Any

import psutil

_logger = logging.getLogger(__name__)

# Same path as disk_guard.CT_DISK_CHECK_PATH
_DISK_CHECK_PATH = "/data/pgcheck"


def collect_host_capacity() -> dict[str, Any]:
    """Return a snapshot of host resource utilisation.

    psutil is a ctpool-only dependency.  The dict is stored inside the
    stats snapshot JSON payload so certsapi can expose it through the
    API without importing psutil itself.

    Returns:
        Dict with keys: ``cpu_percent``, ``memory_total_bytes``,
        ``memory_available_bytes``, ``memory_used_bytes``,
        ``memory_percent``, ``disk_total_bytes``, ``disk_used_bytes``,
        ``disk_free_bytes``, ``disk_percent``,
        ``disk_io_read_bytes``, ``disk_io_write_bytes``,
        ``net_bytes_sent``, ``net_bytes_recv``.
        Any field that cannot be determined is ``None``.
    """
    result: dict[str, Any] = {}
    _collect_cpu(result)
    _collect_memory(result)
    _collect_disk(result)
    _collect_io_counters(result)
    _collect_net_counters(result)
    return result


def _collect_cpu(out: dict[str, Any]) -> None:
    """Populate cpu_percent; interval=None returns the cached value."""
    try:
        out["cpu_percent"] = psutil.cpu_percent(interval=None)
    except Exception:
        _logger.debug("cpu_percent unavailable", exc_info=True)
        out["cpu_percent"] = None


def _collect_memory(out: dict[str, Any]) -> None:
    """Populate memory_* keys from virtual_memory()."""
    try:
        mem = psutil.virtual_memory()
        out["memory_total_bytes"] = mem.total
        out["memory_available_bytes"] = mem.available
        out["memory_used_bytes"] = mem.used
        out["memory_percent"] = mem.percent
    except Exception:
        _logger.debug("virtual_memory unavailable", exc_info=True)
        out["memory_total_bytes"] = None
        out["memory_available_bytes"] = None
        out["memory_used_bytes"] = None
        out["memory_percent"] = None


def _collect_disk(out: dict[str, Any]) -> None:
    """Populate disk_* keys from disk_usage(_DISK_CHECK_PATH).

    Falls back gracefully when the path does not exist (common in dev
    containers or when the data volume is not mounted).
    """
    try:
        disk = psutil.disk_usage(_DISK_CHECK_PATH)
        out["disk_total_bytes"] = disk.total
        out["disk_used_bytes"] = disk.used
        out["disk_free_bytes"] = disk.free
        out["disk_percent"] = disk.percent
    except OSError:
        _logger.debug("disk_usage('%s') unavailable", _DISK_CHECK_PATH)
        out["disk_total_bytes"] = None
        out["disk_used_bytes"] = None
        out["disk_free_bytes"] = None
        out["disk_percent"] = None


def _collect_io_counters(out: dict[str, Any]) -> None:
    """Populate disk I/O keys.  Some VMs return None from disk_io_counters()."""
    try:
        io = psutil.disk_io_counters()
        if io is not None:
            out["disk_io_read_bytes"] = io.read_bytes
            out["disk_io_write_bytes"] = io.write_bytes
        else:
            out["disk_io_read_bytes"] = None
            out["disk_io_write_bytes"] = None
    except Exception:
        _logger.debug("disk_io_counters unavailable", exc_info=True)
        out["disk_io_read_bytes"] = None
        out["disk_io_write_bytes"] = None


def _collect_net_counters(out: dict[str, Any]) -> None:
    """Populate net_bytes_sent/recv.  Some environments return None."""
    try:
        net = psutil.net_io_counters()
        if net is not None:
            out["net_bytes_sent"] = net.bytes_sent
            out["net_bytes_recv"] = net.bytes_recv
        else:
            out["net_bytes_sent"] = None
            out["net_bytes_recv"] = None
    except Exception:
        _logger.debug("net_io_counters unavailable", exc_info=True)
        out["net_bytes_sent"] = None
        out["net_bytes_recv"] = None
