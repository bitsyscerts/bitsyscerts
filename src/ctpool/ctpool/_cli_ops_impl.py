"""Async implementation helpers for the sync-logs, stats, and logs-follow
CLI commands. Also exports progress/status callback factories used by the
tail and backfill commands.

Extracted from cli.py to keep that module under the 500-line limit.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable

from rich.console import Console

from ctpool.config import get_settings
from ctpool.db import create_engine, create_session_factory


def _make_progress_callback(
    console: Console,
) -> Callable[[str, int, int], None]:
    """Return a callback that prints one Rich line per batch to *console*."""

    def _on_batch(log_url: str, count: int, total: int) -> None:
        console.print(
            f"  [cyan]{log_url}[/cyan] +{count:,} entries ([dim]{total:,} total[/dim])"
        )

    return _on_batch


def _make_status_callback(console: Console) -> Callable[[str], None]:
    """Return a callback that prints one-line status messages to *console*."""

    def _on_status(msg: str) -> None:
        console.print(f"[dim]{msg}[/dim]")

    return _on_status


async def run_sync_logs(console: Console) -> None:
    """Async implementation of the sync-logs command."""

    from ctpool.log_discovery import fetch_log_list, sync_log_sources
    from ctpool.log_prober import probe_log

    settings = get_settings()
    engine = create_engine(settings)
    factory = create_session_factory(engine)

    from ctpool.http_client import build_httpx_client

    async with build_httpx_client(settings) as client:
        log_list = await fetch_log_list(client)
        async with factory() as session:
            upserted, operator_count = await sync_log_sources(session, log_list)
            await session.commit()
        console.print(
            f"Synced [cyan]{upserted}[/cyan] logs from "
            f"[cyan]{operator_count}[/cyan] operators."
        )

        healthy = 0
        errors = 0
        async with factory() as session:
            from sqlalchemy import select

            from ctpool.models.log_source import CtLogSource

            result = await session.execute(
                select(CtLogSource).where(CtLogSource.is_eligible_for_tail.is_(True))
            )
            eligible_logs = list(result.scalars().all())

        for log in eligible_logs:
            async with factory() as session:
                try:
                    state = await probe_log(log, client, session)
                    await session.commit()
                    if state.health_status == "ok":
                        healthy += 1
                    else:
                        errors += 1
                except Exception:  # noqa: BLE001
                    errors += 1

    console.print(
        f"Probed [cyan]{len(eligible_logs)}[/cyan] logs — "
        f"[green]{healthy}[/green] healthy, [red]{errors}[/red] errors."
    )
    await engine.dispose()


async def run_stats(watch: bool, console: Console) -> None:
    """Async implementation of the stats command."""
    from ctpool.stats import render_stats, render_stats_watch

    settings = get_settings()
    engine = create_engine(settings)
    factory = create_session_factory(engine)

    if watch:
        await render_stats_watch(factory, console)
    else:
        async with factory() as session:
            await render_stats(session, console)
    await engine.dispose()


async def block_forever() -> None:
    """Await indefinitely; only keyboard interrupt exits."""
    while True:
        await asyncio.sleep(3600)
