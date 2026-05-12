"""Unit tests for ctpool.host_capacity.collect_host_capacity."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from ctpool.host_capacity import collect_host_capacity


def _make_vmem(
    total: int = 8_000_000_000,
    available: int = 4_000_000_000,
    used: int = 3_500_000_000,
    percent: float = 43.75,
) -> SimpleNamespace:
    return SimpleNamespace(total=total, available=available, used=used, percent=percent)


def _make_disk(
    total: int = 100_000_000_000,
    used: int = 50_000_000_000,
    free: int = 50_000_000_000,
    percent: float = 50.0,
) -> SimpleNamespace:
    return SimpleNamespace(total=total, used=used, free=free, percent=percent)


def _make_io_counters(
    read_bytes: int = 1_000_000,
    write_bytes: int = 2_000_000,
) -> SimpleNamespace:
    return SimpleNamespace(read_bytes=read_bytes, write_bytes=write_bytes)


def _make_net_counters(
    bytes_sent: int = 500_000,
    bytes_recv: int = 1_500_000,
) -> SimpleNamespace:
    return SimpleNamespace(bytes_sent=bytes_sent, bytes_recv=bytes_recv)


class TestCollectHostCapacityNormalPath:
    """collect_host_capacity returns populated dict when all psutil calls succeed."""

    def test_returns_all_expected_keys(self) -> None:
        with (
            patch("psutil.cpu_percent", return_value=12.5),
            patch("psutil.virtual_memory", return_value=_make_vmem()),
            patch("psutil.disk_usage", return_value=_make_disk()),
            patch("psutil.disk_io_counters", return_value=_make_io_counters()),
            patch("psutil.net_io_counters", return_value=_make_net_counters()),
        ):
            result = collect_host_capacity()

        expected_keys = {
            "cpu_percent",
            "memory_total_bytes",
            "memory_available_bytes",
            "memory_used_bytes",
            "memory_percent",
            "disk_total_bytes",
            "disk_used_bytes",
            "disk_free_bytes",
            "disk_percent",
            "disk_io_read_bytes",
            "disk_io_write_bytes",
            "net_bytes_sent",
            "net_bytes_recv",
        }
        assert set(result.keys()) == expected_keys

    def test_cpu_percent_is_populated(self) -> None:
        with (
            patch("psutil.cpu_percent", return_value=25.0),
            patch("psutil.virtual_memory", return_value=_make_vmem()),
            patch("psutil.disk_usage", return_value=_make_disk()),
            patch("psutil.disk_io_counters", return_value=_make_io_counters()),
            patch("psutil.net_io_counters", return_value=_make_net_counters()),
        ):
            result = collect_host_capacity()

        assert result["cpu_percent"] == 25.0

    def test_memory_fields_are_populated(self) -> None:
        vmem = _make_vmem(total=8_000, available=4_000, used=3_500, percent=43.75)
        with (
            patch("psutil.cpu_percent", return_value=0.0),
            patch("psutil.virtual_memory", return_value=vmem),
            patch("psutil.disk_usage", return_value=_make_disk()),
            patch("psutil.disk_io_counters", return_value=_make_io_counters()),
            patch("psutil.net_io_counters", return_value=_make_net_counters()),
        ):
            result = collect_host_capacity()

        assert result["memory_total_bytes"] == 8_000
        assert result["memory_available_bytes"] == 4_000
        assert result["memory_used_bytes"] == 3_500
        assert result["memory_percent"] == 43.75

    def test_disk_fields_are_populated(self) -> None:
        disk = _make_disk(total=100, used=50, free=50, percent=50.0)
        with (
            patch("psutil.cpu_percent", return_value=0.0),
            patch("psutil.virtual_memory", return_value=_make_vmem()),
            patch("psutil.disk_usage", return_value=disk),
            patch("psutil.disk_io_counters", return_value=_make_io_counters()),
            patch("psutil.net_io_counters", return_value=_make_net_counters()),
        ):
            result = collect_host_capacity()

        assert result["disk_total_bytes"] == 100
        assert result["disk_used_bytes"] == 50
        assert result["disk_free_bytes"] == 50
        assert result["disk_percent"] == 50.0

    def test_io_counter_fields_are_populated(self) -> None:
        io = _make_io_counters(read_bytes=111, write_bytes=222)
        with (
            patch("psutil.cpu_percent", return_value=0.0),
            patch("psutil.virtual_memory", return_value=_make_vmem()),
            patch("psutil.disk_usage", return_value=_make_disk()),
            patch("psutil.disk_io_counters", return_value=io),
            patch("psutil.net_io_counters", return_value=_make_net_counters()),
        ):
            result = collect_host_capacity()

        assert result["disk_io_read_bytes"] == 111
        assert result["disk_io_write_bytes"] == 222

    def test_net_counter_fields_are_populated(self) -> None:
        net = _make_net_counters(bytes_sent=300, bytes_recv=600)
        with (
            patch("psutil.cpu_percent", return_value=0.0),
            patch("psutil.virtual_memory", return_value=_make_vmem()),
            patch("psutil.disk_usage", return_value=_make_disk()),
            patch("psutil.disk_io_counters", return_value=_make_io_counters()),
            patch("psutil.net_io_counters", return_value=net),
        ):
            result = collect_host_capacity()

        assert result["net_bytes_sent"] == 300
        assert result["net_bytes_recv"] == 600


class TestCollectHostCapacityDiskPathMissing:
    """Disk fields are None when the disk path raises OSError."""

    def test_disk_fields_are_none_on_os_error(self) -> None:
        with (
            patch("psutil.cpu_percent", return_value=5.0),
            patch("psutil.virtual_memory", return_value=_make_vmem()),
            patch("psutil.disk_usage", side_effect=OSError("path not found")),
            patch("psutil.disk_io_counters", return_value=_make_io_counters()),
            patch("psutil.net_io_counters", return_value=_make_net_counters()),
        ):
            result = collect_host_capacity()

        assert result["disk_total_bytes"] is None
        assert result["disk_used_bytes"] is None
        assert result["disk_free_bytes"] is None
        assert result["disk_percent"] is None

    def test_non_disk_fields_still_populated_when_disk_path_missing(self) -> None:
        with (
            patch("psutil.cpu_percent", return_value=10.0),
            patch("psutil.virtual_memory", return_value=_make_vmem()),
            patch("psutil.disk_usage", side_effect=OSError("no mount")),
            patch("psutil.disk_io_counters", return_value=_make_io_counters()),
            patch("psutil.net_io_counters", return_value=_make_net_counters()),
        ):
            result = collect_host_capacity()

        assert result["cpu_percent"] == 10.0
        assert result["memory_total_bytes"] is not None


class TestCollectHostCapacityNoneCounters:
    """None from disk_io_counters / net_io_counters results in None fields."""

    def test_disk_io_none_returns_none_fields(self) -> None:
        with (
            patch("psutil.cpu_percent", return_value=0.0),
            patch("psutil.virtual_memory", return_value=_make_vmem()),
            patch("psutil.disk_usage", return_value=_make_disk()),
            patch("psutil.disk_io_counters", return_value=None),
            patch("psutil.net_io_counters", return_value=_make_net_counters()),
        ):
            result = collect_host_capacity()

        assert result["disk_io_read_bytes"] is None
        assert result["disk_io_write_bytes"] is None

    def test_net_io_none_returns_none_fields(self) -> None:
        with (
            patch("psutil.cpu_percent", return_value=0.0),
            patch("psutil.virtual_memory", return_value=_make_vmem()),
            patch("psutil.disk_usage", return_value=_make_disk()),
            patch("psutil.disk_io_counters", return_value=_make_io_counters()),
            patch("psutil.net_io_counters", return_value=None),
        ):
            result = collect_host_capacity()

        assert result["net_bytes_sent"] is None
        assert result["net_bytes_recv"] is None

    def test_both_io_none_does_not_raise(self) -> None:
        with (
            patch("psutil.cpu_percent", return_value=0.0),
            patch("psutil.virtual_memory", return_value=_make_vmem()),
            patch("psutil.disk_usage", return_value=_make_disk()),
            patch("psutil.disk_io_counters", return_value=None),
            patch("psutil.net_io_counters", return_value=None),
        ):
            result = collect_host_capacity()

        assert result["disk_io_read_bytes"] is None
        assert result["net_bytes_sent"] is None


class TestCollectHostCapacityExceptions:
    """Unexpected exceptions in any collector yield None fields without raising."""

    def test_cpu_exception_yields_none_and_continues(self) -> None:
        with (
            patch("psutil.cpu_percent", side_effect=RuntimeError("no cpu")),
            patch("psutil.virtual_memory", return_value=_make_vmem()),
            patch("psutil.disk_usage", return_value=_make_disk()),
            patch("psutil.disk_io_counters", return_value=_make_io_counters()),
            patch("psutil.net_io_counters", return_value=_make_net_counters()),
        ):
            result = collect_host_capacity()

        assert result["cpu_percent"] is None
        assert result["memory_total_bytes"] is not None

    def test_memory_exception_yields_none_fields(self) -> None:
        with (
            patch("psutil.cpu_percent", return_value=0.0),
            patch("psutil.virtual_memory", side_effect=RuntimeError("no mem")),
            patch("psutil.disk_usage", return_value=_make_disk()),
            patch("psutil.disk_io_counters", return_value=_make_io_counters()),
            patch("psutil.net_io_counters", return_value=_make_net_counters()),
        ):
            result = collect_host_capacity()

        assert result["memory_total_bytes"] is None
        assert result["memory_available_bytes"] is None
