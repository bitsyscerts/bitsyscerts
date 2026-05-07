"""Unit tests for DB contention retry-counter accumulator and rate calculator."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from ctpool.db_contention_observability import _compute_retry_rate
from ctpool.db_contention_store import _RETRY_WINDOW_SECONDS, _accumulate_retry_counts
from ctpool.models.db_contention_state import CtDbContentionState


def _fresh_row() -> CtDbContentionState:
    """Return a minimal in-memory state row with zeroed retry counters."""
    row = CtDbContentionState(
        total_retryable_errors=0,
        retry_window_count=0,
        retry_window_start_at=None,
    )
    return row


_NOW = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)


# ---------------------------------------------------------------------------
# _accumulate_retry_counts
# ---------------------------------------------------------------------------


def test_accumulate_zero_retries_leaves_row_unchanged() -> None:
    row = _fresh_row()
    _accumulate_retry_counts(row, 0, _NOW)
    assert row.total_retryable_errors == 0
    assert row.retry_window_count == 0
    assert row.retry_window_start_at is None


def test_accumulate_first_retry_initialises_window() -> None:
    row = _fresh_row()
    _accumulate_retry_counts(row, 3, _NOW)
    assert row.total_retryable_errors == 3
    assert row.retry_window_count == 3
    assert row.retry_window_start_at == _NOW


def test_accumulate_within_window_increments_both_counters() -> None:
    row = _fresh_row()
    _accumulate_retry_counts(row, 2, _NOW)
    later = _NOW + timedelta(seconds=60)
    _accumulate_retry_counts(row, 5, later)
    assert row.total_retryable_errors == 7
    assert row.retry_window_count == 7
    assert row.retry_window_start_at == _NOW


def test_accumulate_after_window_expiry_resets_window_keeps_total() -> None:
    row = _fresh_row()
    _accumulate_retry_counts(row, 10, _NOW)
    expired = _NOW + timedelta(seconds=_RETRY_WINDOW_SECONDS + 1)
    _accumulate_retry_counts(row, 4, expired)
    assert row.total_retryable_errors == 14
    assert row.retry_window_count == 4
    assert row.retry_window_start_at == expired


def test_accumulate_multiple_calls_accumulate_total_correctly() -> None:
    row = _fresh_row()
    for i in range(5):
        _accumulate_retry_counts(row, 1, _NOW + timedelta(seconds=i))
    assert row.total_retryable_errors == 5


# ---------------------------------------------------------------------------
# _compute_retry_rate
# ---------------------------------------------------------------------------


def test_compute_rate_returns_none_when_window_not_started() -> None:
    assert _compute_retry_rate(0, None, _NOW) is None


def test_compute_rate_returns_zero_when_count_is_zero() -> None:
    start = _NOW - timedelta(seconds=120)
    rate = _compute_retry_rate(0, start, _NOW)
    assert rate is not None
    assert rate == pytest.approx(0.0)


def test_compute_rate_correct_for_known_values() -> None:
    # 10 errors in exactly 2 minutes → 5.0/min
    start = _NOW - timedelta(seconds=120)
    rate = _compute_retry_rate(10, start, _NOW)
    assert rate == pytest.approx(5.0)


def test_compute_rate_clamps_denominator_to_avoid_divide_by_zero() -> None:
    # window_start == now → elapsed clamped to 1 second (1/60 min)
    rate = _compute_retry_rate(6, _NOW, _NOW)
    assert rate is not None
    assert rate > 0.0
