"""Tests for pure pivot-estimation helpers in ctpool.backfill_worker.

``compute_pivot_index`` and ``estimate_log_age_days`` have no external
dependencies (no async, no DB, no HTTP).  Every case is exercised here.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from ctpool.backfill_worker import compute_pivot_index, estimate_log_age_days

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# 2024-01-01 00:00:00 UTC in milliseconds since epoch.
_EPOCH_MS_2024 = int(datetime(2024, 1, 1, tzinfo=UTC).timestamp() * 1000)
# 2024-01-01 00:00:00 UTC as a datetime.
_DT_2024 = datetime(2024, 1, 1, tzinfo=UTC)
# One year ≈ 365.25 days
_YEAR_MS = int(365.25 * 86_400_000)


# ---------------------------------------------------------------------------
# estimate_log_age_days
# ---------------------------------------------------------------------------


def test_estimate_log_age_days_positive_age() -> None:
    """STH timestamp one year after first_seen_at → age ~365.25 days."""
    sth_ms = _EPOCH_MS_2024 + _YEAR_MS
    age = estimate_log_age_days(sth_ms, _DT_2024)
    assert 364.0 < age < 367.0


def test_estimate_log_age_days_zero_age() -> None:
    """STH timestamp equal to first_seen_at epoch → age == 0.0."""
    age = estimate_log_age_days(_EPOCH_MS_2024, _DT_2024)
    assert age == pytest.approx(0.0, abs=0.001)


def test_estimate_log_age_days_negative_age_clamped_to_zero() -> None:
    """STH timestamp before first_seen_at → clamped to 0.0."""
    sth_ms = _EPOCH_MS_2024 - _YEAR_MS  # one year *before* first_seen_at
    age = estimate_log_age_days(sth_ms, _DT_2024)
    assert age == 0.0


def test_estimate_log_age_days_multi_year() -> None:
    """A 5-year-old log should return approximately 1826 days."""
    sth_ms = _EPOCH_MS_2024 + 5 * _YEAR_MS
    age = estimate_log_age_days(sth_ms, _DT_2024)
    assert 1820.0 < age < 1835.0


def test_estimate_log_age_days_none_first_seen_returns_zero() -> None:
    """first_seen_at=None → returns 0.0 (unknown creation date)."""
    age = estimate_log_age_days(_EPOCH_MS_2024 + _YEAR_MS, None)
    assert age == 0.0


# ---------------------------------------------------------------------------
# compute_pivot_index
# ---------------------------------------------------------------------------


def test_compute_pivot_index_days_zero_returns_zero() -> None:
    """days=0 means full history → pivot = 0."""
    assert compute_pivot_index(1_000_000, 0, 365.0) == 0


def test_compute_pivot_index_log_age_zero_returns_zero() -> None:
    """log_age_days=0 → can't estimate pivot → full history."""
    assert compute_pivot_index(1_000_000, 90, 0.0) == 0


def test_compute_pivot_index_tree_size_zero_returns_zero() -> None:
    """Empty log → nothing to index."""
    assert compute_pivot_index(0, 90, 365.0) == 0


def test_compute_pivot_index_days_exceed_log_age_returns_zero() -> None:
    """Requesting more days than the log is old → full history."""
    assert compute_pivot_index(1_000_000, 400, 365.0) == 0


def test_compute_pivot_index_days_equal_log_age_returns_zero() -> None:
    """days == log_age_days → still full history (nothing to skip)."""
    assert compute_pivot_index(1_000_000, 365, 365.0) == 0


def test_compute_pivot_index_normal_case() -> None:
    """90 days of a 360-day log → skip 75% → pivot at 750,000 of 1,000,000."""
    # fraction_to_skip = 1 - 90/360 = 0.75
    pivot = compute_pivot_index(1_000_000, 90, 360.0)
    assert pivot == 750_000


def test_compute_pivot_index_never_returns_tree_size() -> None:
    """pivot is always < tree_size (clamped to tree_size - 1)."""
    pivot = compute_pivot_index(10, 1, 365.0)
    assert pivot < 10
