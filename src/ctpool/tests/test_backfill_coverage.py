"""Tests for backfill_coverage — pure coverage math."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from ctpool.backfill_coverage import (
    _FALLBACK_ENTRIES_PER_DAY,
    compute_extended_start,
    coverage_reached,
    coverage_target_date,
    estimate_extension_entries,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_UTC = UTC

# Fixed base so relative deltas are exact and tests are not timing-sensitive.
_BASE = datetime(2026, 5, 11, 12, 0, 0, tzinfo=_UTC)


def _dt(days_ago: float) -> datetime:
    return _BASE - timedelta(days=days_ago)


# ---------------------------------------------------------------------------
# coverage_target_date
# ---------------------------------------------------------------------------


class TestCoverageTargetDate:
    def test_returns_utc_aware(self) -> None:
        result = coverage_target_date(30)
        assert result.tzinfo is not None

    def test_roughly_n_days_ago(self) -> None:
        result = coverage_target_date(30)
        # Allow a 1-second tolerance for test execution time.
        delta = datetime.now(tz=_UTC) - result
        assert abs(delta.total_seconds() - 30 * 86_400) < 1.0

    def test_zero_days_is_now(self) -> None:
        result = coverage_target_date(0)
        delta = datetime.now(tz=_UTC) - result
        assert abs(delta.total_seconds()) < 1.0


# ---------------------------------------------------------------------------
# coverage_reached
# ---------------------------------------------------------------------------


class TestCoverageReached:
    def test_none_oldest_returns_false(self) -> None:
        assert coverage_reached(None, _dt(30)) is False

    def test_oldest_before_target_returns_true(self) -> None:
        oldest = _dt(35)  # 35 days ago — before the 30-day target
        target = _dt(30)
        assert coverage_reached(oldest, target) is True

    def test_oldest_exactly_at_target_returns_true(self) -> None:
        target = _dt(30)
        assert coverage_reached(target, target) is True

    def test_oldest_after_target_returns_false(self) -> None:
        oldest = _dt(25)  # 25 days ago — newer than the 30-day target
        target = _dt(30)
        assert coverage_reached(oldest, target) is False


# ---------------------------------------------------------------------------
# estimate_extension_entries
# ---------------------------------------------------------------------------


class TestEstimateExtensionEntries:
    def test_normal_density(self) -> None:
        # Batch of 86_400 entries spanning exactly 1 day → 86_400/day.
        oldest = _dt(2)
        newest = _dt(1)
        result = estimate_extension_entries(86_400, oldest, newest, missing_days=1.0)
        assert result == 86_400

    def test_fractional_missing_days(self) -> None:
        oldest = _dt(2)
        newest = _dt(1)
        result = estimate_extension_entries(86_400, oldest, newest, missing_days=0.5)
        assert result == 43_200

    def test_zero_missing_days_returns_one(self) -> None:
        oldest = _dt(2)
        newest = _dt(1)
        result = estimate_extension_entries(100, oldest, newest, missing_days=0.0)
        assert result == 1

    def test_negative_missing_days_returns_one(self) -> None:
        oldest = _dt(2)
        newest = _dt(1)
        result = estimate_extension_entries(100, oldest, newest, missing_days=-5.0)
        assert result == 1

    def test_degenerate_zero_span_uses_fallback(self) -> None:
        # oldest == newest → span < 1 second → fallback density
        same = _dt(1)
        result = estimate_extension_entries(100, same, same, missing_days=1.0)
        assert result == _FALLBACK_ENTRIES_PER_DAY

    def test_zero_entries_uses_fallback(self) -> None:
        oldest = _dt(2)
        newest = _dt(1)
        result = estimate_extension_entries(0, oldest, newest, missing_days=1.0)
        assert result == _FALLBACK_ENTRIES_PER_DAY

    def test_result_always_at_least_one(self) -> None:
        # Very tiny batch but non-zero span and non-zero missing_days
        oldest = _dt(31)
        newest = _dt(30)
        result = estimate_extension_entries(1, oldest, newest, missing_days=0.00001)
        assert result >= 1


# ---------------------------------------------------------------------------
# compute_extended_start
# ---------------------------------------------------------------------------


class TestComputeExtendedStart:
    def test_normal_extension(self) -> None:
        assert compute_extended_start(100_000, 20_000) == 80_000

    def test_floors_at_zero(self) -> None:
        assert compute_extended_start(1_000, 5_000) == 0

    def test_exactly_zero(self) -> None:
        assert compute_extended_start(5_000, 5_000) == 0

    def test_large_current_start(self) -> None:
        assert compute_extended_start(10_000_000, 1_000_000) == 9_000_000
