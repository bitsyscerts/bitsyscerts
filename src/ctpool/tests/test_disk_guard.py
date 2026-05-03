"""Tests for ctpool.disk_guard — disk space threshold checks."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from ctpool.disk_guard import get_free_disk_gb, is_disk_critical, is_disk_low
from ctpool.exceptions import DiskGuardError


def test_get_free_disk_gb_returns_positive_float() -> None:
    """Returns a positive float for the root filesystem."""
    result = get_free_disk_gb("/")
    assert isinstance(result, float)
    assert result > 0.0


def test_get_free_disk_gb_nonexistent_path_raises_disk_guard_error() -> None:
    """Raises DiskGuardError for a path that does not exist."""
    with pytest.raises(DiskGuardError):
        get_free_disk_gb("/this/path/does/not/exist/at/all")


def test_is_disk_low_true_when_free_below_threshold() -> None:
    """Returns True when free space is below the low threshold."""
    with patch("ctpool.disk_guard.get_free_disk_gb", return_value=5.0):
        assert is_disk_low(min_free_gb=50) is True


def test_is_disk_low_false_when_free_above_threshold() -> None:
    """Returns False when free space exceeds the low threshold."""
    with patch("ctpool.disk_guard.get_free_disk_gb", return_value=200.0):
        assert is_disk_low(min_free_gb=50) is False


def test_is_disk_critical_true_when_free_below_critical() -> None:
    """Returns True when free space is below the critical threshold."""
    with patch("ctpool.disk_guard.get_free_disk_gb", return_value=1.0):
        assert is_disk_critical(critical_free_gb=20) is True


def test_is_disk_critical_false_when_free_above_critical() -> None:
    """Returns False when free space exceeds the critical threshold."""
    with patch("ctpool.disk_guard.get_free_disk_gb", return_value=100.0):
        assert is_disk_critical(critical_free_gb=20) is False


def test_is_disk_low_boundary_exactly_at_threshold() -> None:
    """Returns False when free space equals the threshold (not strictly below)."""
    with patch("ctpool.disk_guard.get_free_disk_gb", return_value=50.0):
        assert is_disk_low(min_free_gb=50) is False


def test_is_disk_critical_boundary_exactly_at_threshold() -> None:
    """Returns False when free space equals the critical threshold."""
    with patch("ctpool.disk_guard.get_free_disk_gb", return_value=20.0):
        assert is_disk_critical(critical_free_gb=20) is False
