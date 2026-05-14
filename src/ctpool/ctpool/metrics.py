"""Per-log ingestion metrics accumulator and retention pruning.

# File consolidation rationale (201-500 lines warning zone):
# All exports here serve a single concern: tracking and pruning per-log
# ingestion metrics.  LogMetricsAccumulator and the prune helpers share the
# IngestionMetric ORM model and are always used together.  Splitting into two
# modules would add an artificial boundary with no domain separation benefit.
# Consolidation is justified until a third distinct metrics concern is added.

Exports:
    LogMetricsAccumulator — Thread-safe counter bag with snapshot persistence.
    MetricsPruneState     — Monotonic-clock gate for interval-bounded pruning.
    prune_ingestion_metrics — Delete old ingestion_metrics rows.
    maybe_prune_metrics   — Call prune at most once per configured interval.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ctpool.entry_write_result import EntryWriteMetrics
from ctpool.models.ingestion_metric import IngestionMetric


class LogMetricsAccumulator:
    """Accumulate ingestion counters and persist periodic snapshots.

    One instance per log worker.  All ``record_*`` methods are synchronous
    (they only mutate Python integers) so they may be called from any async
    or sync context.  Only ``persist_snapshot`` touches the database.
    """

    def __init__(self) -> None:
        self._entries_fetched: int = 0
        self._entries_parsed: int = 0
        self._certs_upserted: int = 0
        self._hostnames_upserted: int = 0
        self._new_unique_certificates: int = 0
        self._duplicate_certificates: int = 0
        self._new_unique_hostnames: int = 0
        self._known_hostnames: int = 0
        self._retryable_errors: int = 0
        self._terminal_entry_errors: int = 0
        self._parse_errors: int = 0
        self._http_429_count: int = 0
        self._http_5xx_count: int = 0
        self._window_start: float = time.monotonic()

    def record_entries_fetched(self, count: int) -> None:
        """Add *count* to the entries-fetched counter."""
        self._entries_fetched += count

    def record_entries_parsed(self, count: int) -> None:
        """Add *count* to the entries-parsed counter."""
        self._entries_parsed += count

    def record_certs_upserted(self, count: int) -> None:
        """Add *count* to the certs-upserted counter."""
        self._certs_upserted += count

    def record_hostnames_upserted(self, count: int) -> None:
        """Add *count* to the hostnames-upserted counter."""
        self._hostnames_upserted += count

    def record_entry_write_metrics(self, metrics: EntryWriteMetrics) -> None:
        """Add one stored entry's uniqueness and hostname counts."""
        self._certs_upserted += (
            metrics.new_unique_certificates + metrics.duplicate_certificates
        )
        self._hostnames_upserted += metrics.hostnames_observed
        self._new_unique_certificates += metrics.new_unique_certificates
        self._duplicate_certificates += metrics.duplicate_certificates
        self._new_unique_hostnames += metrics.new_unique_hostnames
        self._known_hostnames += metrics.known_hostnames

    def record_retryable_errors(self, count: int) -> None:
        """Add *count* to the retryable-error counter."""
        self._retryable_errors += count

    def record_terminal_entry_errors(self, count: int) -> None:
        """Add *count* to the terminal-entry-error counter."""
        self._terminal_entry_errors += count

    def record_parse_error(self) -> None:
        """Increment the parse-error counter by one."""
        self._parse_errors += 1

    def record_http_429(self) -> None:
        """Increment the HTTP-429 counter by one."""
        self._http_429_count += 1

    def record_http_5xx(self) -> None:
        """Increment the HTTP-5xx counter by one."""
        self._http_5xx_count += 1

    def has_activity(self) -> bool:
        """Return True when the current window contains any metrics activity."""
        return any(
            (
                self._entries_fetched,
                self._entries_parsed,
                self._certs_upserted,
                self._hostnames_upserted,
                self._new_unique_certificates,
                self._duplicate_certificates,
                self._new_unique_hostnames,
                self._known_hostnames,
                self._retryable_errors,
                self._terminal_entry_errors,
                self._parse_errors,
                self._http_429_count,
                self._http_5xx_count,
            )
        )

    def get_snapshot(self, window_seconds: int = 60) -> dict[str, int | float]:
        """Return the current counters as a plain dict.

        Args:
            window_seconds: Nominal window duration to associate with this snapshot.

        Returns:
            Dict with all counters plus calculated throughput.
        """
        elapsed = max(time.monotonic() - self._window_start, 0.001)
        throughput = self._entries_fetched / elapsed
        return {
            "window_seconds": window_seconds,
            "entries_fetched": self._entries_fetched,
            "entries_parsed": self._entries_parsed,
            "certs_upserted": self._certs_upserted,
            "hostnames_upserted": self._hostnames_upserted,
            "new_unique_certificates": self._new_unique_certificates,
            "duplicate_certificates": self._duplicate_certificates,
            "new_unique_hostnames": self._new_unique_hostnames,
            "known_hostnames": self._known_hostnames,
            "retryable_errors": self._retryable_errors,
            "terminal_entry_errors": self._terminal_entry_errors,
            "parse_errors": self._parse_errors,
            "http_429_count": self._http_429_count,
            "http_5xx_count": self._http_5xx_count,
            "throughput_entries_per_sec": throughput,
        }

    async def persist_snapshot(
        self,
        session: AsyncSession,
        log_source_id: uuid.UUID,
        window_seconds: int = 60,
    ) -> None:
        """Write a snapshot row to ``ingestion_metrics`` and reset counters.

        Args:
            session:        Active async database session.
            log_source_id:  UUID of the CT log being ingested.
            window_seconds: Nominal window duration for this snapshot.
        """
        snap = self.get_snapshot(window_seconds)
        metric = IngestionMetric(
            log_source_id=log_source_id,
            snapshot_at=datetime.now(UTC),
            window_seconds=snap["window_seconds"],
            entries_fetched=snap["entries_fetched"],
            entries_parsed=snap["entries_parsed"],
            certs_upserted=snap["certs_upserted"],
            hostnames_upserted=snap["hostnames_upserted"],
            new_unique_certificates=snap["new_unique_certificates"],
            duplicate_certificates=snap["duplicate_certificates"],
            new_unique_hostnames=snap["new_unique_hostnames"],
            known_hostnames=snap["known_hostnames"],
            retryable_errors=snap["retryable_errors"],
            terminal_entry_errors=snap["terminal_entry_errors"],
            parse_errors=snap["parse_errors"],
            http_429_count=snap["http_429_count"],
            http_5xx_count=snap["http_5xx_count"],
            throughput_entries_per_sec=snap["throughput_entries_per_sec"],
        )
        session.add(metric)
        self._reset()

    def _reset(self) -> None:
        """Reset all counters and restart the window timer."""
        self._entries_fetched = 0
        self._entries_parsed = 0
        self._certs_upserted = 0
        self._hostnames_upserted = 0
        self._new_unique_certificates = 0
        self._duplicate_certificates = 0
        self._new_unique_hostnames = 0
        self._known_hostnames = 0
        self._retryable_errors = 0
        self._terminal_entry_errors = 0
        self._parse_errors = 0
        self._http_429_count = 0
        self._http_5xx_count = 0
        self._window_start = time.monotonic()


# ---------------------------------------------------------------------------
# Retention pruning
# ---------------------------------------------------------------------------


async def prune_ingestion_metrics(
    session: AsyncSession,
    retention_days: int,
    *,
    dry_run: bool = False,
) -> int:
    """Delete ``ingestion_metrics`` rows older than *retention_days*.

    Args:
        session:        Active async database session (no transaction needed;
                        the function opens its own if not dry-run).
        retention_days: Rows with ``snapshot_at`` older than this many days
                        will be deleted.
        dry_run:        If True, count rows that *would* be deleted without
                        actually deleting them.

    Returns:
        Number of rows deleted (or that would be deleted on dry-run).
    """
    cutoff = datetime.now(UTC) - timedelta(days=retention_days)
    if dry_run:
        result = await session.execute(
            select(func.count()).where(IngestionMetric.snapshot_at < cutoff)
        )
        return int(result.scalar_one())
    result = await session.execute(
        delete(IngestionMetric)
        .where(IngestionMetric.snapshot_at < cutoff)
        .returning(IngestionMetric.id)
    )
    return result.rowcount


@dataclass
class MetricsPruneState:
    """Monotonic-clock state for at-most-once-per-interval pruning.

    One instance per worker process.  Reset between test runs.
    """

    last_pruned_at: float = field(default_factory=lambda: 0.0)


async def maybe_prune_metrics(
    state: MetricsPruneState,
    session: AsyncSession,
    retention_days: int,
    prune_interval_seconds: int,
) -> int:
    """Prune old metrics rows if the configured interval has elapsed.

    Args:
        state:                 Mutable prune-state object shared by the worker.
        session:               Active async database session.
        retention_days:        Passed through to :func:`prune_ingestion_metrics`.
        prune_interval_seconds: Minimum seconds between automatic prune runs.

    Returns:
        Number of rows deleted, or 0 if the interval has not elapsed yet.
    """
    now = time.monotonic()
    if now - state.last_pruned_at < prune_interval_seconds:
        return 0
    deleted = await prune_ingestion_metrics(session, retention_days)
    state.last_pruned_at = now
    return deleted
