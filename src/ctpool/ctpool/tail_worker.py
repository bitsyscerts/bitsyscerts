"""CT log tail worker: continuously tail new entries from all eligible logs.

Exports:
    run_tail           — Tail loop entry point; one session per batch.
    reset_tail_cursors — Reset all tail cursors to the current tree edge.
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
    advance_tail_cursor,
    ensure_tail_cursor,
    get_eligible_tail_logs,
    reset_tail_cursor,
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
    batch_size: int,
    metrics: LogMetricsAccumulator,
    limit_remaining: int | None,
    *,
    init_from_end: int = 0,
) -> tuple[int, bool]:
    """Fetch and write one batch of entries for *log*.

    Returns:
        ``(entries_processed, is_empty)`` — count written and whether the
        response had zero entries (caller should sleep before retrying).
    """
    # This function is ~55 lines — justified by sequential async steps that
    # form an atomic unit of work and cannot be split without inverting control.
    sth = await fetch_sth(log.url, client)
    tree_size: int = sth.tree_size

    init_index = max(0, tree_size - init_from_end)
    cursor, was_created = await ensure_tail_cursor(
        session, log.id, init_index=init_index
    )
    if was_created:
        mode = "recent sample" if init_from_end else "current edge"
        _logger.info(
            "Initialized tail cursor for %s at %s: tree_size=%d, tail_next_index=%d",
            log.description,
            mode,
            tree_size,
            init_index,
        )

    start = cursor.next_index
    if start >= tree_size:
        return 0, True

    batch = batch_size
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
        except Exception as exc:  # pragma: no cover
            _logger.warning(
                "unexpected cert error log=%s index=%d: %s",
                log.id,
                start + i,
                exc,
            )
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
    client: httpx.AsyncClient,
    metrics: LogMetricsAccumulator,
    *,
    batch_size: int,
    limit_remaining: int | None,
    init_from_end: int = 0,
) -> tuple[int, bool]:
    """Run one tail batch for *log* in its own session/transaction.

    Returns:
        ``(entries_processed, is_empty)``
    """
    async with session_factory() as session:
        async with session.begin():
            try:
                count, is_empty = await _process_log_batch(
                    log,
                    session,
                    client,
                    batch_size,
                    metrics,
                    limit_remaining,
                    init_from_end=init_from_end,
                )
                if count > 0:
                    await metrics.persist_snapshot(session, log.id)
                return count, is_empty
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
    on_batch: Callable[[str, int, int], None] | None = None,
    on_status: Callable[[str], None] | None = None,
    init_from_end: int = 0,
    batch_size: int | None = None,
) -> None:
    """Main tail worker loop.

    Continuously fetches new entries from eligible CT logs starting at their
    tail cursor.  On first run (no cursor exists), the cursor is initialized
    to the current tree edge so only newly appended entries are fetched.
    Pass ``init_from_end=N`` to initialize the cursor N entries before the
    edge instead (for development sampling).

    Args:
        session_factory: Factory for creating database sessions.
        settings:        Validated application settings.
        once:            Exit after one full pass over all eligible logs.
        limit:           Stop after processing this many total entries.
        log_id:          Restrict to a single CT log UUID.
        on_batch:        Optional callback(log_url, batch_count, total_count)
                         called after each non-empty batch. Use for progress
                         reporting; omit for silent/daemon operation.
        init_from_end:   When creating a new cursor, start this many entries
                         before the current tree edge (default 0 = edge).
    """
    _logger.info("tail worker starting worker_id=%s", _worker_id())
    total_processed = 0
    _batch = batch_size or settings.ct_default_batch_size
    client = httpx.AsyncClient(timeout=settings.ct_http_timeout_seconds)

    async with client:
        while True:
            if is_disk_critical(
                settings.ct_critical_free_disk_gb, settings.ct_disk_check_path
            ):
                _logger.critical("disk critical — halting tail worker")
                # Exit non-zero so Docker applies restart backoff instead of
                # immediately relaunching and looping on the same condition.
                raise SystemExit(1)

            if is_disk_low(settings.ct_min_free_disk_gb, settings.ct_disk_check_path):
                _logger.warning(
                    "disk low — pausing tail for %ds", _SLEEP_DISK_LOW_SECONDS
                )
                if on_status is not None:
                    on_status(f"Disk low — pausing {_SLEEP_DISK_LOW_SECONDS} s")
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
                    client,
                    metrics,
                    batch_size=_batch,
                    limit_remaining=limit_remaining,
                    init_from_end=init_from_end,
                )
                total_processed += processed
                if processed > 0 and on_batch is not None:
                    on_batch(log.url, processed, total_processed)
                if not is_empty:
                    any_empty = False

            if once:
                return

            if any_empty:
                _logger.debug(
                    "tail: no new entries — sleeping %ds",
                    settings.ct_tail_interval_seconds,
                )
                if on_status is not None:
                    on_status(
                        f"All logs at tree edge — sleeping"
                        f" {settings.ct_tail_interval_seconds} s"
                    )
                await asyncio.sleep(settings.ct_tail_interval_seconds)


async def reset_tail_cursors(
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
    *,
    log_id: _uuid.UUID | None = None,
) -> None:
    """Reset tail cursors to the current tree edge for all eligible logs.

    Probes each eligible log's STH, then overwrites its tail cursor's
    ``next_index`` to the live ``tree_size``.  Old and new values are
    logged at INFO level for auditability.

    # This function is ~35 lines — justified by the per-log HTTP probe +
    # DB reset that form an indivisible audit unit; splitting would lose
    # per-log error isolation.

    Args:
        session_factory: Factory for creating database sessions.
        settings:        Validated application settings.
        log_id:          If set, restrict to a single log UUID.
    """
    client = httpx.AsyncClient(timeout=settings.ct_http_timeout_seconds)
    async with client:
        async with session_factory() as session:
            logs = await get_eligible_tail_logs(session)

        if log_id is not None:
            logs = [lg for lg in logs if lg.id == log_id]

        for log in logs:
            try:
                sth = await fetch_sth(log.url, client)
                tree_size = sth.tree_size
            except FetchError as exc:
                _logger.error("reset: STH probe failed log=%s: %s", log.id, exc)
                continue

            try:
                async with session_factory() as session:
                    async with session.begin():
                        old_index = await reset_tail_cursor(session, log.id, tree_size)
                _logger.info(
                    "Reset tail cursor for %s: old_tail_next_index=%d, "
                    "new_tail_next_index=%d",
                    log.description,
                    old_index,
                    tree_size,
                )
            except ValueError:
                _logger.warning("No cursor to reset for log=%s; skipping", log.id)
