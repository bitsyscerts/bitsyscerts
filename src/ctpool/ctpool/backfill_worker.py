"""CT log backfill worker: claim and process historical index ranges.

Exports:
    run_backfill — Backfill loop entry point; one session per range claim.
"""

from __future__ import annotations

import asyncio
import logging
import socket
import uuid as _uuid
from collections.abc import Callable
from os import getpid

import httpx
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ctpool.config import Settings
from ctpool.disk_guard import is_disk_critical, is_disk_low
from ctpool.dispatcher import (
    claim_backfill_range,
    create_backfill_ranges,
    get_eligible_backfill_logs,
    mark_range_complete,
    mark_range_failed,
)
from ctpool.exceptions import FetchError, ParseError
from ctpool.fetcher import fetch_entries, fetch_sth
from ctpool.metrics import LogMetricsAccumulator
from ctpool.models.log_backfill_range import CtLogBackfillRange
from ctpool.models.log_source import CtLogSource
from ctpool.normalizer import build_normalized_entry
from ctpool.parser import parse_leaf_entry
from ctpool.writer import write_normalized_entry

_logger = logging.getLogger(__name__)

_SLEEP_NO_RANGES_SECONDS = 30
_SLEEP_DISK_LOW_SECONDS = 60


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
    days: int | None,
) -> None:
    """Probe a log's STH and create backfill ranges if none exist yet.

    ``days`` is accepted for future use (estimating start offset); currently
    the full tree is seeded starting from index 0.
    """
    try:
        sth = await fetch_sth(log.url, client)
    except FetchError as exc:
        _logger.error("backfill seed: STH probe failed log=%s: %s", log.id, exc)
        return

    tree_size: int = sth.tree_size
    if tree_size == 0:
        return

    async with session_factory() as session:
        async with session.begin():
            count = await create_backfill_ranges(session, log, 0, tree_size - 1)

    if count:
        _logger.info(
            "backfill seeded %d ranges log=%s tree_size=%d", count, log.id, tree_size
        )


async def _process_range_batch(
    claimed: CtLogBackfillRange,
    log_url: str,
    session: AsyncSession,
    client: httpx.AsyncClient,
    settings: Settings,
    metrics: LogMetricsAccumulator,
    limit_remaining: int | None,
) -> int:
    """Fetch and write one batch of entries within *claimed*.

    Returns the number of entries successfully written.
    """
    start = claimed.next_index
    batch = settings.ct_default_batch_size
    if limit_remaining is not None:
        batch = min(batch, limit_remaining)
    end = min(start + batch - 1, claimed.end_index)

    response = await fetch_entries(log_url, start, end, client)
    count = 0
    for i, raw_entry in enumerate(response.entries):
        try:
            parsed = parse_leaf_entry(raw_entry.leaf_input)
            normalized = build_normalized_entry(
                parsed, claimed.log_source_id, start + i
            )
            await write_normalized_entry(session, normalized)
            count += 1
        except ParseError as exc:
            _logger.warning(
                "parse error backfill range=%s index=%d: %s",
                claimed.id,
                start + i,
                exc,
            )
            metrics.record_parse_error()
        except Exception as exc:  # pragma: no cover
            _logger.warning(
                "unexpected cert error backfill range=%s index=%d: %s",
                claimed.id,
                start + i,
                exc,
            )
            metrics.record_parse_error()

    metrics.record_entries_fetched(len(response.entries))
    metrics.record_entries_parsed(count)
    metrics.record_certs_upserted(count)
    return count


async def _run_one_range(
    claimed: CtLogBackfillRange,
    session_factory: async_sessionmaker[AsyncSession],
    client: httpx.AsyncClient,
    settings: Settings,
    limit_remaining: int | None,
) -> tuple[int, str]:
    """Process *claimed* range; mark complete or failed.

    Returns:
        ``(entries_written, log_url)`` — count and the URL of the parent log.
    """
    metrics = LogMetricsAccumulator()
    try:
        async with session_factory() as session:
            async with session.begin():
                log_url = await _resolve_log_url(session, claimed)
                count = await _process_range_batch(
                    claimed,
                    log_url,
                    session,
                    client,
                    settings,
                    metrics,
                    limit_remaining,
                )

        async with session_factory() as session:
            async with session.begin():
                await mark_range_complete(session, claimed.id)

        return count, log_url
    except FetchError as exc:
        _logger.error("fetch error backfill range=%s: %s", claimed.id, exc)
        async with session_factory() as session:
            async with session.begin():
                await mark_range_failed(session, claimed.id, str(exc))
        return 0, ""


async def run_backfill(
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
    *,
    once: bool = False,
    limit: int | None = None,
    days: int | None = None,
    log_id: _uuid.UUID | None = None,
    on_batch: Callable[[str, int, int], None] | None = None,
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
    client = httpx.AsyncClient(timeout=settings.ct_http_timeout_seconds)

    async with client:
        async with session_factory() as session:
            logs = await get_eligible_backfill_logs(session)
        if log_id is not None:
            logs = [lg for lg in logs if lg.id == log_id]
        for log in logs:
            await _seed_ranges_for_log(log, session_factory, settings, client, days)

        while True:
            if is_disk_critical(settings.ct_critical_free_disk_gb):
                _logger.critical("disk critical — halting backfill worker")
                break

            if is_disk_low(settings.ct_min_free_disk_gb):
                _logger.warning(
                    "disk low — pausing backfill for %ds", _SLEEP_DISK_LOW_SECONDS
                )
                await asyncio.sleep(_SLEEP_DISK_LOW_SECONDS)
                if once:
                    break
                continue

            if limit is not None and total_processed >= limit:
                return

            limit_remaining = (limit - total_processed) if limit is not None else None

            async with session_factory() as session:
                async with session.begin():
                    claimed = await claim_backfill_range(session, log_id, worker)

            if claimed is None:
                _logger.debug(
                    "backfill: no pending ranges — sleeping %ds",
                    _SLEEP_NO_RANGES_SECONDS,
                )
                if once:
                    return
                await asyncio.sleep(_SLEEP_NO_RANGES_SECONDS)
                continue

            batch_count, log_url = await _run_one_range(
                claimed, session_factory, client, settings, limit_remaining
            )
            total_processed += batch_count
            if batch_count > 0 and on_batch is not None:
                on_batch(log_url, batch_count, total_processed)

            if once:
                return
