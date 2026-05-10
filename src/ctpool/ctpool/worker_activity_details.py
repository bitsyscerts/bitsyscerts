"""Helpers for projecting batch metrics into worker heartbeat payloads."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Any

from ctpool.metrics import LogMetricsAccumulator
from ctpool.worker_registry import WorkerCounters


def build_worker_runtime_details(
    snapshot: Mapping[str, int | float],
    *,
    checkpoint_index: int | None = None,
    retry_count: int | None = None,
    next_retry_at: datetime | None = None,
    rate_limited_until: datetime | None = None,
    extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return normalized worker-detail fields derived from a metrics snapshot."""
    observations_per_min = float(snapshot.get("throughput_entries_per_sec", 0.0)) * 60.0
    entries_fetched = int(snapshot.get("entries_fetched", 0))
    per_observation_multiplier = (
        observations_per_min / float(entries_fetched) if entries_fetched > 0 else 0.0
    )

    details: dict[str, Any] = {
        "observations_per_min": observations_per_min,
        "new_unique_certificates_per_min": (
            int(snapshot.get("new_unique_certificates", 0)) * per_observation_multiplier
        ),
        "duplicate_certificates_per_min": (
            int(snapshot.get("duplicate_certificates", 0)) * per_observation_multiplier
        ),
        "new_unique_hostnames_per_min": (
            int(snapshot.get("new_unique_hostnames", 0)) * per_observation_multiplier
        ),
        "known_hostnames_per_min": (
            int(snapshot.get("known_hostnames", 0)) * per_observation_multiplier
        ),
    }
    if checkpoint_index is not None:
        details["checkpoint_index"] = checkpoint_index
    if retry_count is not None:
        details["retry_count"] = retry_count
    if next_retry_at is not None:
        details["next_retry_at"] = next_retry_at.isoformat()
    if rate_limited_until is not None:
        details["rate_limited_until"] = rate_limited_until.isoformat()
    if extra is not None:
        for key, value in extra.items():
            if value is not None:
                details[key] = value
    return details


def build_worker_counters(
    metrics: LogMetricsAccumulator,
    *,
    last_error_type: str | None = None,
    last_error_message: str | None = None,
    checkpoint_index: int | None = None,
    retry_count: int | None = None,
    next_retry_at: datetime | None = None,
    rate_limited_until: datetime | None = None,
    extra: Mapping[str, Any] | None = None,
) -> WorkerCounters:
    """Build a heartbeat-ready WorkerCounters payload from batch metrics."""
    snapshot = metrics.get_snapshot()
    return WorkerCounters(
        processed_entries=int(snapshot["entries_fetched"]),
        stored_certificates=int(snapshot["certs_upserted"]),
        duplicate_certificates=int(snapshot["duplicate_certificates"]),
        observed_hostnames=int(snapshot["hostnames_upserted"]),
        new_hostnames=int(snapshot["new_unique_hostnames"]),
        parse_errors=int(snapshot["parse_errors"]),
        retryable_errors=int(snapshot["retryable_errors"]),
        terminal_errors=int(snapshot["terminal_entry_errors"]),
        last_error_type=last_error_type,
        last_error_message=last_error_message,
        extra=build_worker_runtime_details(
            snapshot,
            checkpoint_index=checkpoint_index,
            retry_count=retry_count,
            next_retry_at=next_retry_at,
            rate_limited_until=rate_limited_until,
            extra=extra,
        ),
    )
