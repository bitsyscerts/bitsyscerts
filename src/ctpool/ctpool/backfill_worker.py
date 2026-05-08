"""CT log backfill worker: claim and process historical index ranges.

Exports:
    estimate_log_age_days — Pure helper: estimate a log's age in days from STH
                            timestamp and first_seen_at.
    compute_pivot_index   — Pure helper: calculate the start index for a
                            days-bounded backfill window.
    run_backfill          — Backfill loop entry point; one session per range claim.
"""

from __future__ import annotations

import asyncio
import logging
import socket
import time
import uuid as _uuid
from collections.abc import Callable
from datetime import datetime
from os import getpid

import httpx
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ctpool.config import Settings
from ctpool.db_contention_accumulator import DbRetryPressureAccumulator
from ctpool.db_contention_coordinator import (
    build_db_retry_callback,
    get_db_contention_directive,
    resolve_effective_batch_size,
    sleep_for_db_contention,
    submit_db_contention_observation,
)
from ctpool.db_contention_types import DbContentionObservation
from ctpool.disk_guard import is_disk_critical, is_disk_low
from ctpool.dispatcher import (
    claim_backfill_range,
    create_backfill_ranges,
    get_eligible_backfill_logs,
    has_backfill_ranges,
    mark_range_complete,
    mark_range_failed,
    mark_range_pending,
    reap_stale_backfill_claims,
    update_range_heartbeat,
)
from ctpool.entry_persistence import persist_entry_with_retry, persist_failure_outcome
from ctpool.exceptions import (
    FetchError,
    ParseError,
    RateLimitError,
    UnsupportedEntryTypeError,
)
from ctpool.fetcher import fetch_entries, fetch_sth
from ctpool.metrics import LogMetricsAccumulator
from ctpool.models.log_backfill_range import CtLogBackfillRange
from ctpool.models.log_source import CtLogSource
from ctpool.normalizer import build_normalized_entry
from ctpool.outcome_constants import OUTCOME_PARSE_ERROR, OUTCOME_UNSUPPORTED_ENTRY_TYPE
from ctpool.parser import parse_leaf_entry

_logger = logging.getLogger(__name__)

_SLEEP_NO_RANGES_SECONDS = 30
_SLEEP_DISK_LOW_SECONDS = 60

# Milliseconds-per-day constant used by the pivot estimation.
_MS_PER_DAY: float = 86_400_000.0


def estimate_log_age_days(
    sth_timestamp_ms: int,
    first_seen_at: datetime | None,
) -> float:
    """Return a CT log's approximate age in days.

    Uses the STH millisecond timestamp as *now* and ``first_seen_at`` as the
    log creation proxy.  Returns ``0.0`` if the result would be negative or
    ``first_seen_at`` is ``None``.

    Args:
        sth_timestamp_ms: Milliseconds since epoch from the log's signed tree head.
        first_seen_at:    When this log was first observed (from ``CtLogSource``).
                          ``None`` is treated as unknown → returns ``0.0``.

    Returns:
        Age in days as a float, minimum ``0.0``.
    """
    if first_seen_at is None:
        return 0.0
    first_seen_ms = first_seen_at.timestamp() * 1000.0
    age_ms = sth_timestamp_ms - first_seen_ms
    return max(0.0, age_ms / _MS_PER_DAY)


def compute_pivot_index(
    tree_size: int,
    days: int,
    log_age_days: float,
) -> int:
    """Return the start index for a days-bounded backfill window.

    Estimates the index corresponding to ``days`` ago by assuming uniform
    certificate issuance over the log's lifetime.  Returns ``0`` when the
    window covers the full history or the age estimate is not usable.

    Args:
        tree_size:    Current tree size (number of entries in the log).
        days:         How far back to backfill (0 means full history).
        log_age_days: Estimated total age of the log in days.

    Returns:
        First index to include; always in ``[0, tree_size)``.
    """
    if tree_size == 0 or days <= 0 or log_age_days <= 0 or days >= log_age_days:
        return 0
    fraction_to_skip = 1.0 - (days / log_age_days)
    return max(0, min(int(tree_size * fraction_to_skip), tree_size - 1))


def _worker_id() -> str:
    """Return a stable identity string: ``hostname:PID``."""
    return f"{socket.gethostname()}:{getpid()}"


async def _resolve_log_url(session: AsyncSession, claimed: CtLogBackfillRange) -> str:
    """Return the URL for the CT log that owns *claimed*.

    Raises:
        FetchError: If the parent CtLogSource row is not found.
    """
    log = await session.get(CtLogSource, claimed.log_source_id)
    if log is None:
        raise FetchError(
            f"CtLogSource {claimed.log_source_id} not found for range {claimed.id}"
        )
    return log.url


async def _seed_ranges_for_log(
    log: CtLogSource,
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
    client: httpx.AsyncClient,
    days: int,
    on_status: Callable[[str], None] | None = None,
) -> None:
    """Probe a log's STH and create backfill ranges if none exist yet.

    When *days* is greater than zero, only ranges covering the most recent
    *days* days of history are seeded (pivot estimated from tree uniformity).
    Pass ``days=0`` to seed the full history from index 0.
    """
    try:
        async with session_factory() as session:
            if await has_backfill_ranges(session, log.id):
                return

        if on_status is not None:
            on_status(f"Seeding {log.description} — probing tree size…")
        sth = await fetch_sth(log.url, client)
    except FetchError as exc:
        _logger.error("backfill seed: STH probe failed log=%s: %s", log.id, exc)
        if on_status is not None:
            on_status(f"  Seed failed for {log.description}: {exc}")
        return

    tree_size: int = sth.tree_size
    if tree_size == 0:
        return

    log_age_days = estimate_log_age_days(sth.timestamp, log.first_seen_at)
    pivot = compute_pivot_index(tree_size, days, log_age_days)

    async with session_factory() as session:
        async with session.begin():
            count = await create_backfill_ranges(session, log, pivot, tree_size - 1)

    if count:
        if on_status is not None:
            on_status(
                f"  └ seeded {count:,} ranges"
                f" ({tree_size - pivot:,} entries) for {log.description}"
            )
        _logger.info(
            "backfill seeded %d ranges log=%s tree_size=%d pivot=%d",
            count,
            log.id,
            tree_size,
            pivot,
        )


async def _process_range_batch(
    claimed: CtLogBackfillRange,
    log_url: str,
    session: AsyncSession,
    client: httpx.AsyncClient,
    batch_size: int,
    metrics: LogMetricsAccumulator,
    limit_remaining: int | None,
    settings: Settings,
) -> tuple[int, DbContentionObservation]:
    """Fetch and write one batch of entries within *claimed*.

    Returns the number of entries successfully written plus one retry sample.
    """
    start = claimed.next_index
    batch = batch_size
    if limit_remaining is not None:
        batch = min(batch, limit_remaining)
    end = min(start + batch - 1, claimed.end_index)

    response = await fetch_entries(log_url, start, end, client)
    count = 0
    hostname_count = 0
    retry_accumulator = DbRetryPressureAccumulator()
    for i, raw_entry in enumerate(response.entries):
        entry_index = start + i
        try:
            parsed = parse_leaf_entry(raw_entry.leaf_input)
            normalized = build_normalized_entry(
                parsed, claimed.log_source_id, entry_index
            )

            def _on_retry(
                attempt: int,
                exc: BaseException,
                delay: float,
                *,
                idx: int = entry_index,
            ) -> None:
                _logger.warning(
                    "deadlock retry backfill range=%s index=%d attempt=%d "
                    "delay=%.3fs: %s",
                    claimed.id,
                    idx,
                    attempt,
                    delay,
                    exc,
                )

            retry_accumulator.record_entry_attempt()
            await persist_entry_with_retry(
                session,
                normalized,
                max_retries=settings.ct_deadlock_max_retries,
                base_backoff_seconds=settings.ct_deadlock_base_backoff_seconds,
                max_backoff_seconds=settings.ct_deadlock_max_backoff_seconds,
                on_retry=build_db_retry_callback(retry_accumulator, _on_retry),
            )
            count += 1
            hostname_count += len(normalized.hostnames)
        except UnsupportedEntryTypeError as exc:
            _logger.warning(
                "unsupported entry type backfill range=%s index=%d: %s",
                claimed.id,
                entry_index,
                exc,
            )
            metrics.record_parse_error()
            await persist_failure_outcome(
                session,
                claimed.log_source_id,
                entry_index,
                OUTCOME_UNSUPPORTED_ENTRY_TYPE,
                exc,
            )
        except ParseError as exc:
            _logger.warning(
                "parse error backfill range=%s index=%d: %s",
                claimed.id,
                entry_index,
                exc,
            )
            metrics.record_parse_error()
            await persist_failure_outcome(
                session,
                claimed.log_source_id,
                entry_index,
                OUTCOME_PARSE_ERROR,
                exc,
            )
        except Exception as exc:  # pragma: no cover
            _logger.warning(
                "unexpected cert error backfill range=%s index=%d type=%s detail=%r",
                claimed.id,
                entry_index,
                exc.__class__.__name__,
                exc,
            )

    metrics.record_entries_fetched(len(response.entries))
    metrics.record_entries_parsed(count)
    metrics.record_certs_upserted(count)
    metrics.record_hostnames_upserted(hostname_count)
    return count, retry_accumulator.drain()


async def _run_one_range(
    claimed: CtLogBackfillRange,
    session_factory: async_sessionmaker[AsyncSession],
    client: httpx.AsyncClient,
    settings: Settings,
    batch_size: int,
    limit_remaining: int | None,
) -> tuple[int, str, bool, DbContentionObservation, int | None]:
    """Process *claimed* range; mark complete or failed.

    Returns:
        ``(entries_written, log_url, was_rate_limited, contention,
        retry_after_seconds)``.
    """
    metrics = LogMetricsAccumulator()
    try:
        async with session_factory() as session:
            async with session.begin():
                log_url = await _resolve_log_url(session, claimed)
            async with session.begin():
                await update_range_heartbeat(session, claimed.id)
            count, observation = await _process_range_batch(
                claimed,
                log_url,
                session,
                client,
                batch_size,
                metrics,
                limit_remaining,
                settings,
            )
            if count > 0:
                async with session.begin():
                    await metrics.persist_snapshot(session, claimed.log_source_id)

        async with session_factory() as session:
            async with session.begin():
                await mark_range_complete(session, claimed.id)

        return count, log_url, False, observation, None
    except RateLimitError as exc:
        _logger.warning("rate limited backfill range=%s: %s", claimed.id, exc)
        async with session_factory() as session:
            async with session.begin():
                await mark_range_pending(session, claimed.id)
        return 0, "", True, DbContentionObservation(0, 0), exc.retry_after_seconds
    except FetchError as exc:
        _logger.error("fetch error backfill range=%s: %s", claimed.id, exc)
        async with session_factory() as session:
            async with session.begin():
                await mark_range_failed(session, claimed.id, str(exc))
        return 0, "", False, DbContentionObservation(0, 0), None
    except Exception as exc:
        _logger.error(
            "unexpected error backfill range=%s type=%s: %s",
            claimed.id,
            exc.__class__.__name__,
            exc,
        )
        async with session_factory() as session:
            async with session.begin():
                await mark_range_failed(session, claimed.id, str(exc))
        return 0, "", False, DbContentionObservation(0, 0), None


async def run_backfill(
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
    *,
    once: bool = False,
    limit: int | None = None,
    days: int | None = None,
    log_id: _uuid.UUID | None = None,
    on_batch: Callable[[str, int, int], None] | None = None,
    on_status: Callable[[str], None] | None = None,
    batch_size: int | None = None,
) -> None:
    """Main backfill worker loop.

    Claims pending ranges from the database and processes them sequentially.
    Seeds new ranges from the current STH on first run. Pauses when disk is
    low; halts when disk is critical.

    Args:
        session_factory: Factory for creating database sessions.
        settings:        Validated application settings.
        once:            Exit after processing one range.
        limit:           Stop after this many total entries.
        days:            Override ct_backfill_days for range seeding.
        log_id:          Restrict to a single CT log UUID.
        on_batch:        Optional callback(log_url, batch_count, total_count)
                         called after each non-empty range. Use for progress
                         reporting; omit for silent/daemon operation.
    """
    worker = _worker_id()
    _logger.info("backfill worker starting worker_id=%s", worker)
    total_processed = 0
    _batch = batch_size or settings.ct_default_batch_size
    _days: int = days if days is not None else settings.ct_backfill_days
    client = httpx.AsyncClient(timeout=settings.ct_http_timeout_seconds)
    rate_limited_until: dict[_uuid.UUID, float] = {}
    rate_limit_hits: dict[_uuid.UUID, int] = {}

    async with client:
        async with session_factory() as session:
            logs = await get_eligible_backfill_logs(session)
        if log_id is not None:
            logs = [lg for lg in logs if lg.id == log_id]
        for log in logs:
            await _seed_ranges_for_log(
                log, session_factory, settings, client, _days, on_status
            )

        while True:
            if is_disk_critical(
                settings.ct_critical_free_disk_gb, settings.ct_disk_check_path
            ):
                _logger.critical("disk critical — halting backfill worker")
                # Exit non-zero so Docker applies restart backoff instead of
                # immediately relaunching and looping on the same condition.
                raise SystemExit(1)

            if is_disk_low(settings.ct_min_free_disk_gb, settings.ct_disk_check_path):
                _logger.warning(
                    "disk low — pausing backfill for %ds", _SLEEP_DISK_LOW_SECONDS
                )
                if on_status is not None:
                    on_status(f"Disk low — pausing {_SLEEP_DISK_LOW_SECONDS} s")
                await asyncio.sleep(_SLEEP_DISK_LOW_SECONDS)
                if once:
                    break
                continue

            if limit is not None and total_processed >= limit:
                return

            limit_remaining = (limit - total_processed) if limit is not None else None
            now = time.monotonic()
            excluded_log_ids = {
                lid for lid, until in rate_limited_until.items() if now < until
            }

            async with session_factory() as session:
                async with session.begin():
                    reaped = await reap_stale_backfill_claims(
                        session,
                        settings.ct_backfill_claim_timeout_seconds,
                    )
            if reaped:
                _logger.info("backfill reaper: reset %d stale claims", len(reaped))
                for r in reaped:
                    _logger.debug(
                        "backfill reaper: range=%s log=%s next_index=%d",
                        r.id,
                        r.log_source_id,
                        r.next_index,
                    )

            directive = await get_db_contention_directive(
                session_factory,
                settings,
                _batch,
            )
            effective_batch = resolve_effective_batch_size(_batch, directive)
            db_sleep = await sleep_for_db_contention(directive, settings)
            if db_sleep > 0.0 and on_status is not None:
                on_status(f"DB contention — pacing {db_sleep:.2f} s")

            async with session_factory() as session:
                async with session.begin():
                    claimed = await claim_backfill_range(
                        session,
                        log_id,
                        worker,
                        excluded_log_source_ids=excluded_log_ids,
                    )

            if claimed is None:
                _logger.debug(
                    "backfill: no pending ranges — sleeping %ds",
                    _SLEEP_NO_RANGES_SECONDS,
                )
                if on_status is not None:
                    on_status(
                        f"No pending ranges — sleeping {_SLEEP_NO_RANGES_SECONDS} s"
                    )
                if once:
                    return
                await asyncio.sleep(_SLEEP_NO_RANGES_SECONDS)
                continue

            if on_status is not None:
                on_status(
                    f"Fetching [{claimed.start_index:,}–{claimed.end_index:,}]"
                    f" ({claimed.end_index - claimed.start_index + 1:,} entries)…"
                )
            (
                batch_count,
                log_url,
                was_rate_limited,
                observation,
                retry_after,
            ) = await _run_one_range(
                claimed,
                session_factory,
                client,
                settings,
                effective_batch,
                limit_remaining,
            )
            if was_rate_limited:
                hit_count = rate_limit_hits.get(claimed.log_source_id, 0) + 1
                rate_limit_hits[claimed.log_source_id] = hit_count
                if retry_after is not None:
                    backoff_seconds: float = min(
                        settings.ct_retry_after_max_seconds, retry_after
                    )
                else:
                    backoff_seconds = min(
                        settings.ct_rate_limit_backoff_max_seconds,
                        settings.ct_rate_limit_backoff_seconds * (2 ** (hit_count - 1)),
                    )
                rate_limited_until[claimed.log_source_id] = now + float(backoff_seconds)
                if on_status is not None:
                    on_status(
                        "Rate limited for log "
                        f"{claimed.log_source_id} — pausing {backoff_seconds} s"
                    )
                if once:
                    return
                continue

            if observation.has_activity:
                await submit_db_contention_observation(
                    session_factory,
                    settings,
                    observation,
                    _batch,
                )

            if batch_count == 0 and on_status is not None:
                on_status("  └ fetch error — range marked failed")

            if batch_count > 0:
                rate_limit_hits.pop(claimed.log_source_id, None)
                rate_limited_until.pop(claimed.log_source_id, None)

            total_processed += batch_count
            if batch_count > 0 and on_batch is not None:
                on_batch(log_url, batch_count, total_processed)

            if once:
                return
