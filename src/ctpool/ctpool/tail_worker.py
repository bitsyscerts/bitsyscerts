"""CT log tail worker: continuously tail new entries from all eligible logs.

Exports:
    run_tail — Tail loop entry point; one session per batch.
"""

from __future__ import annotations

import asyncio
import logging
import socket
import uuid as _uuid
from os import getpid

import httpx
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ctpool.config import Settings
from ctpool.disk_guard import is_disk_critical, is_disk_low
from ctpool.dispatcher import (
    advance_tail_cursor,
    ensure_tail_cursor,
    get_eligible_tail_logs,
)
from ctpool.exceptions import FetchError, ParseError
from ctpool.fetcher import fetch_entries, fetch_sth
from ctpool.metrics import LogMetricsAccumulator
from ctpool.models.log_source import CtLogSource
from ctpool.normalizer import build_normalized_entry
from ctpool.parser import parse_leaf_entry
from ctpool.writer import write_normalized_entry

_logger = logging.getLogger(__name__)

_SLEEP_EMPTY_SECONDS = 30
_SLEEP_DISK_LOW_SECONDS = 60


def _worker_id() -> str:
    """Return a stable identity string: ``hostname:PID``."""
    return f"{socket.gethostname()}:{getpid()}"


async def _process_log_batch(
    log: CtLogSource,
    session: AsyncSession,
    client: httpx.AsyncClient,
    settings: Settings,
    metrics: LogMetricsAccumulator,
    limit_remaining: int | None,
) -> tuple[int, bool]:
    """Fetch and write one batch of entries for *log*.

    Returns:
        ``(entries_processed, is_empty)`` — count written and whether the
        response had zero entries (caller should sleep before retrying).
    """
    # This function is ~45 lines — justified by sequential async steps that
    # form an atomic unit of work and cannot be split without inverting control.
    cursor = await ensure_tail_cursor(session, log.id)
    sth = await fetch_sth(log.url, client)
    tree_size: int = sth.tree_size

    start = cursor.next_index
    if start >= tree_size:
        return 0, True

    batch = settings.ct_default_batch_size
    if limit_remaining is not None:
        batch = min(batch, limit_remaining)
    end = min(start + batch - 1, tree_size - 1)

    response = await fetch_entries(log.url, start, end, client)
    entries = response.entries
    if not entries:
        return 0, True

    count = 0
    for i, raw_entry in enumerate(entries):
        try:
            parsed = parse_leaf_entry(raw_entry.leaf_input)
            normalized = build_normalized_entry(parsed, log.id, start + i)
            await write_normalized_entry(session, normalized)
            count += 1
        except ParseError as exc:
            _logger.warning("parse error log=%s index=%d: %s", log.id, start + i, exc)
            metrics.record_parse_error()

    metrics.record_entries_fetched(len(entries))
    metrics.record_entries_parsed(count)
    metrics.record_certs_upserted(count)

    next_index = start + len(entries)
    await advance_tail_cursor(session, log.id, next_index)
    return count, False


async def _tail_one_log(
    log: CtLogSource,
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
    client: httpx.AsyncClient,
    metrics: LogMetricsAccumulator,
    *,
    limit_remaining: int | None,
) -> tuple[int, bool]:
    """Run one tail batch for *log* in its own session/transaction.

    Returns:
        ``(entries_processed, is_empty)``
    """
    async with session_factory() as session:
        async with session.begin():
            try:
                return await _process_log_batch(
                    log, session, client, settings, metrics, limit_remaining
                )
            except FetchError as exc:
                _logger.error("fetch error tail log=%s: %s", log.id, exc)
                return 0, False


async def run_tail(
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
    *,
    once: bool = False,
    limit: int | None = None,
    log_id: _uuid.UUID | None = None,
) -> None:
    """Main tail worker loop.

    Continuously fetches new entries from eligible CT logs starting at their
    tail cursor. Pauses when disk is low; stops when ``limit`` entries have
    been processed or ``once=True``.

    Args:
        session_factory: Factory for creating database sessions.
        settings:        Validated application settings.
        once:            Exit after one full pass over all eligible logs.
        limit:           Stop after processing this many total entries.
        log_id:          Restrict to a single CT log UUID.
    """
    _logger.info("tail worker starting worker_id=%s", _worker_id())
    total_processed = 0
    client = httpx.AsyncClient(timeout=settings.ct_http_timeout_seconds)

    async with client:
        while True:
            if is_disk_critical(settings.ct_critical_free_disk_gb):
                _logger.critical("disk critical — halting tail worker")
                break

            if is_disk_low(settings.ct_min_free_disk_gb):
                _logger.warning(
                    "disk low — pausing tail for %ds", _SLEEP_DISK_LOW_SECONDS
                )
                await asyncio.sleep(_SLEEP_DISK_LOW_SECONDS)
                if once:
                    break
                continue

            async with session_factory() as session:
                logs = await get_eligible_tail_logs(session)

            if log_id is not None:
                logs = [lg for lg in logs if lg.id == log_id]

            any_empty = True
            for log in logs:
                if limit is not None and total_processed >= limit:
                    return

                limit_remaining = (
                    (limit - total_processed) if limit is not None else None
                )
                metrics = LogMetricsAccumulator()
                processed, is_empty = await _tail_one_log(
                    log,
                    session_factory,
                    settings,
                    client,
                    metrics,
                    limit_remaining=limit_remaining,
                )
                total_processed += processed
                if not is_empty:
                    any_empty = False

            if once:
                return

            if any_empty:
                _logger.debug(
                    "tail: no new entries — sleeping %ds",
                    settings.ct_tail_interval_seconds,
                )
                await asyncio.sleep(settings.ct_tail_interval_seconds)
