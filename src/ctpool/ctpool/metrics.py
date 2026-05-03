"""Per-log ingestion metrics accumulator.

Exports:
    LogMetricsAccumulator — Thread-safe counter bag with snapshot persistence.
"""

from __future__ import annotations

import time
import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

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

    def record_parse_error(self) -> None:
        """Increment the parse-error counter by one."""
        self._parse_errors += 1

    def record_http_429(self) -> None:
        """Increment the HTTP-429 counter by one."""
        self._http_429_count += 1

    def record_http_5xx(self) -> None:
        """Increment the HTTP-5xx counter by one."""
        self._http_5xx_count += 1

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
        self._parse_errors = 0
        self._http_429_count = 0
        self._http_5xx_count = 0
        self._window_start = time.monotonic()
