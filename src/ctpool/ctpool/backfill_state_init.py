"""Per-log backfill state initializer.

Probes a CT log's signed tree head and writes a ``ct_log_backfill_state``
row with the configured backfill window. This is the per-log replacement
for the legacy range-seeding path; instead of materializing many range
rows, the window is represented as two indices on a single state row.

Exports:
    initialize_backfill_state_for_log — Probe STH and seed window for one log.
"""

from __future__ import annotations

import logging
from collections.abc import Callable

import httpx
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ctpool.backfill_pivot import compute_pivot_index, estimate_log_age_days
from ctpool.exceptions import FetchError
from ctpool.fetcher import fetch_sth
from ctpool.models.log_source import CtLogSource
from ctpool.worker_claim import (
    ensure_log_backfill_state,
    initialize_log_window,
)

_logger = logging.getLogger(__name__)


async def initialize_backfill_state_for_log(
    log: CtLogSource,
    session_factory: async_sessionmaker[AsyncSession],
    client: httpx.AsyncClient,
    days: int,
    on_status: Callable[[str], None] | None = None,
) -> None:
    """Ensure a ``ct_log_backfill_state`` row exists with a configured window.

    The window covers the most recent *days* of log history (or full history
    when ``days == 0``). The pivot is computed using the same uniform-issuance
    estimate used by the legacy range seeder, so the per-log dispatch model
    covers the same indices as the legacy model.

    Idempotent: if a window is already set and the log is not yet complete,
    only re-aligns bounds when the log has grown (``backfill_end_index`` is
    advanced to ``tree_size - 1``); the checkpoint is preserved.

    Args:
        log:             The CT log source to initialize.
        session_factory: Factory for creating database sessions.
        client:          HTTP client for STH probes.
        days:            Days of history to backfill; 0 means full history.
        on_status:       Optional callback for operator-visible status strings.
    """
    try:
        if on_status is not None:
            on_status(f"Initializing {log.description} — probing tree size…")
        sth = await fetch_sth(log.url, client)
    except FetchError as exc:
        _logger.error("backfill state init: STH probe failed log=%s: %s", log.id, exc)
        if on_status is not None:
            on_status(f"  Init failed for {log.description}: {exc}")
        return

    tree_size: int = sth.tree_size
    if tree_size == 0:
        return

    log_age_days = estimate_log_age_days(sth.timestamp, log.first_seen_at)
    pivot = compute_pivot_index(tree_size, days, log_age_days)
    end_index = tree_size - 1

    async with session_factory() as session:
        async with session.begin():
            await ensure_log_backfill_state(session, log_source_id=log.id)
            await initialize_log_window(
                session,
                log_source_id=log.id,
                backfill_start_index=pivot,
                backfill_end_index=end_index,
            )

    if on_status is not None:
        on_status(
            f"  └ window [{pivot:,}–{end_index:,}]"
            f" ({end_index - pivot + 1:,} entries) for {log.description}"
        )
    _logger.info(
        "backfill state initialized log=%s tree_size=%d pivot=%d end=%d",
        log.id,
        tree_size,
        pivot,
        end_index,
    )
