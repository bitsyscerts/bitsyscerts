"""CT backfill range seeder: probe a log's STH and seed initial ranges.

Exports:
    seed_ranges_for_log — Probe STH and create backfill ranges when none exist.
"""

from __future__ import annotations

import logging
from collections.abc import Callable

import httpx
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ctpool.backfill_pivot import compute_pivot_index, estimate_log_age_days
from ctpool.config import Settings
from ctpool.dispatcher import create_backfill_ranges, has_backfill_ranges
from ctpool.exceptions import FetchError
from ctpool.fetcher import fetch_sth
from ctpool.models.log_source import CtLogSource

_logger = logging.getLogger(__name__)


async def seed_ranges_for_log(
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

    Args:
        log:             The CT log source to seed.
        session_factory: Factory for creating database sessions.
        settings:        Validated application settings (unused directly but
                         passed for future extensibility).
        client:          HTTP client for STH probes.
        days:            Days of history to backfill; 0 means full history.
        on_status:       Optional callback for operator-visible status strings.
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
