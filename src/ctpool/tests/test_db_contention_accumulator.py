"""Tests for worker-local DB retry pressure accumulation."""

from __future__ import annotations

from ctpool.db_contention_accumulator import DbRetryPressureAccumulator


def test_drain_returns_attempts_and_retries_then_resets() -> None:
    accumulator = DbRetryPressureAccumulator()
    accumulator.record_entry_attempt()
    accumulator.record_entry_attempt()
    accumulator.record_retryable_error()

    first = accumulator.drain()
    second = accumulator.drain()

    assert first.entries_attempted == 2
    assert first.retryable_errors == 1
    assert second.entries_attempted == 0
    assert second.retryable_errors == 0


def test_wrap_retry_callback_records_and_delegates() -> None:
    accumulator = DbRetryPressureAccumulator()
    calls: list[tuple[int, str, float]] = []

    def _callback(attempt: int, exc: BaseException, delay: float) -> None:
        calls.append((attempt, str(exc), delay))

    wrapped = accumulator.wrap_retry_callback(_callback)
    wrapped(2, RuntimeError("deadlock"), 0.25)
    observation = accumulator.drain()

    assert observation.retryable_errors == 1
    assert calls == [(2, "deadlock", 0.25)]
