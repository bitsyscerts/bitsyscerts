"""Tests for worker heartbeat detail helpers."""

from __future__ import annotations

from datetime import UTC, datetime

from ctpool.entry_write_result import EntryWriteMetrics
from ctpool.metrics import LogMetricsAccumulator
from ctpool.worker_activity_details import (
    build_worker_counters,
    build_worker_runtime_details,
)


def test_build_worker_runtime_details_computes_per_minute_rates() -> None:
    """Per-minute activity rates derive from snapshot throughput and counts."""
    snapshot = {
        "entries_fetched": 120,
        "new_unique_certificates": 30,
        "duplicate_certificates": 90,
        "new_unique_hostnames": 12,
        "known_hostnames": 48,
        "throughput_entries_per_sec": 2.0,
    }
    next_retry_at = datetime(2025, 1, 1, tzinfo=UTC)
    rate_limited_until = datetime(2025, 1, 1, 0, 5, tzinfo=UTC)

    details = build_worker_runtime_details(
        snapshot,
        checkpoint_index=500,
        retry_count=2,
        next_retry_at=next_retry_at,
        rate_limited_until=rate_limited_until,
    )

    assert details["observations_per_min"] == 120.0
    assert details["new_unique_certificates_per_min"] == 30.0
    assert details["duplicate_certificates_per_min"] == 90.0
    assert details["new_unique_hostnames_per_min"] == 12.0
    assert details["known_hostnames_per_min"] == 48.0
    assert details["checkpoint_index"] == 500
    assert details["retry_count"] == 2
    assert details["next_retry_at"] == next_retry_at.isoformat()
    assert details["rate_limited_until"] == rate_limited_until.isoformat()


def test_build_worker_counters_maps_metrics_and_error_fields() -> None:
    """Worker counters mirror batch metrics and carry normalized detail fields."""
    metrics = LogMetricsAccumulator()
    metrics.record_entries_fetched(10)
    metrics.record_retryable_errors(1)
    metrics.record_terminal_entry_errors(2)
    metrics.record_parse_error()
    metrics.record_entry_write_metrics(
        EntryWriteMetrics(
            new_unique_certificates=3,
            duplicate_certificates=7,
            hostnames_observed=5,
            new_unique_hostnames=2,
            known_hostnames=3,
        )
    )

    counters = build_worker_counters(
        metrics,
        last_error_type="FetchError",
        last_error_message="boom",
        checkpoint_index=25,
    )

    assert counters.processed_entries == 10
    assert counters.stored_certificates == 10
    assert counters.duplicate_certificates == 7
    assert counters.observed_hostnames == 5
    assert counters.new_hostnames == 2
    assert counters.parse_errors == 1
    assert counters.retryable_errors == 1
    assert counters.terminal_errors == 2
    assert counters.last_error_type == "FetchError"
    assert counters.last_error_message == "boom"
    assert counters.extra["checkpoint_index"] == 25
