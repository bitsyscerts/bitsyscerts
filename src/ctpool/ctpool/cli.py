"""Typer CLI for ctpool.

Commands:
    db-init              — Run Alembic migrations to head.
    db-status            — Show current schema revision and DB connectivity.
    sync-logs            — Fetch CT log list, upsert sources, probe each log.
    tail                 — Run the tail worker loop.
    backfill             — Run the backfill worker loop.
    stats                — Display per-log ingestion statistics.
    logs-follow          — Stream application log output to the terminal.
    reset-tail-cursors   — Reset tail cursors to the current tree edge.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import Callable
from typing import Annotated

import typer
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


app = typer.Typer(name="ctpool", no_args_is_help=True, add_completion=False)
_console = Console()


# ---------------------------------------------------------------------------
# db-init
# ---------------------------------------------------------------------------


@app.command("db-init")
def db_init() -> None:
    """Run Alembic migrations to head (idempotent)."""
    from ctpool.migration_runner import run_upgrade_head

    settings = get_settings()
    asyncio.run(run_upgrade_head(settings))
    _console.print("[green]Database schema is up to date.[/green]")


# ---------------------------------------------------------------------------
# db-status
# ---------------------------------------------------------------------------


@app.command("db-status")
def db_status() -> None:
    """Show the current Alembic revision and DB connectivity."""
    from ctpool.migration_runner import get_current_revision

    settings = get_settings()
    revision = asyncio.run(get_current_revision(settings))
    if revision is None:
        _console.print(
            "[yellow]No migrations applied (schema not initialised).[/yellow]"
        )
    else:
        _console.print(f"Current revision: [cyan]{revision}[/cyan]")


# ---------------------------------------------------------------------------
# sync-logs
# ---------------------------------------------------------------------------


@app.command("sync-logs")
def sync_logs() -> None:
    """Fetch the CT log list, upsert log sources, and probe each log."""
    asyncio.run(_run_sync_logs())


async def _run_sync_logs() -> None:
    """Async implementation of sync-logs."""
    import httpx

    from ctpool.log_discovery import fetch_log_list, sync_log_sources
    from ctpool.log_prober import probe_log

    settings = get_settings()
    engine = create_engine(settings)
    factory = create_session_factory(engine)

    async with httpx.AsyncClient(timeout=settings.ct_http_timeout_seconds) as client:
        log_list = await fetch_log_list(client)
        async with factory() as session:
            upserted, operator_count = await sync_log_sources(session, log_list)
            await session.commit()
        _console.print(
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

    _console.print(
        f"Probed [cyan]{len(eligible_logs)}[/cyan] logs — "
        f"[green]{healthy}[/green] healthy, [red]{errors}[/red] errors."
    )
    await engine.dispose()


# ---------------------------------------------------------------------------
# tail
# ---------------------------------------------------------------------------


@app.command("tail")
def tail(
    once: Annotated[bool, typer.Option("--once", help="Exit after one pass.")] = False,
    limit: Annotated[
        int | None, typer.Option("--limit", help="Stop after N entries.")
    ] = None,
    log_id: Annotated[
        uuid.UUID | None, typer.Option("--log-id", help="Restrict to one log UUID.")
    ] = None,
    progress: Annotated[
        bool, typer.Option("--progress", help="Print a line per batch.")
    ] = False,
    init_from_end: Annotated[
        int,
        typer.Option(
            "--init-from-end",
            help=(
                "On first run (no cursor), start this many entries before the "
                "current tree edge. Default 0 means start at the edge and "
                "process only new entries. Use e.g. 10000 for a recent sample."
            ),
        ),
    ] = 0,
) -> None:
    """Tail new CT log entries continuously."""
    from ctpool.tail_worker import run_tail

    settings = get_settings()
    engine = create_engine(settings)
    factory = create_session_factory(engine)
    on_batch = _make_progress_callback(_console) if progress else None
    asyncio.run(
        run_tail(
            factory,
            settings,
            once=once,
            limit=limit,
            log_id=log_id,
            on_batch=on_batch,
            init_from_end=init_from_end,
        )
    )


# ---------------------------------------------------------------------------
# reset-tail-cursors
# ---------------------------------------------------------------------------


@app.command("reset-tail-cursors")
def reset_tail_cursors_cmd(
    to_current: Annotated[
        bool,
        typer.Option(
            "--to-current",
            help="Required: confirm that cursors should be reset to the current edge.",
        ),
    ] = False,
    log_id: Annotated[
        uuid.UUID | None,
        typer.Option("--log-id", help="Restrict to one log UUID."),
    ] = None,
) -> None:
    """Reset tail cursors to the current tree edge (requires --to-current)."""
    if not to_current:
        _console.print(
            "[red]Error:[/red] Pass --to-current to confirm the reset. "
            "This will move all tail cursors to the live tree edge."
        )
        raise typer.Exit(code=1)
    from ctpool.tail_worker import reset_tail_cursors

    settings = get_settings()
    engine = create_engine(settings)
    factory = create_session_factory(engine)
    asyncio.run(reset_tail_cursors(factory, settings, log_id=log_id))


# ---------------------------------------------------------------------------
# backfill
# ---------------------------------------------------------------------------


@app.command("backfill")
def backfill(
    once: Annotated[
        bool, typer.Option("--once", help="Process one range then exit.")
    ] = False,
    limit: Annotated[
        int | None, typer.Option("--limit", help="Stop after N entries.")
    ] = None,
    days: Annotated[
        int | None, typer.Option("--days", help="Override CT_BACKFILL_DAYS.")
    ] = None,
    log_id: Annotated[
        uuid.UUID | None, typer.Option("--log-id", help="Restrict to one log UUID.")
    ] = None,
    progress: Annotated[
        bool, typer.Option("--progress", help="Print a line per batch.")
    ] = False,
) -> None:
    """Claim and process historical CT log backfill ranges."""
    from ctpool.backfill_worker import run_backfill

    settings = get_settings()
    engine = create_engine(settings)
    factory = create_session_factory(engine)
    on_batch = _make_progress_callback(_console) if progress else None
    asyncio.run(
        run_backfill(
            factory,
            settings,
            once=once,
            limit=limit,
            days=days,
            log_id=log_id,
            on_batch=on_batch,
        )
    )


# ---------------------------------------------------------------------------
# stats
# ---------------------------------------------------------------------------


@app.command("stats")
def stats(
    watch: Annotated[
        bool, typer.Option("--watch", help="Refresh every 5 seconds.")
    ] = False,
) -> None:
    """Display per-log ingestion statistics."""
    asyncio.run(_run_stats(watch=watch))


async def _run_stats(watch: bool) -> None:
    """Async implementation of stats."""
    from ctpool.stats import render_stats, render_stats_watch

    settings = get_settings()
    engine = create_engine(settings)
    factory = create_session_factory(engine)

    if watch:
        await render_stats_watch(factory, _console)
    else:
        async with factory() as session:
            await render_stats(session, _console)
    await engine.dispose()


# ---------------------------------------------------------------------------
# logs-follow
# ---------------------------------------------------------------------------


@app.command("logs-follow")
def logs_follow(
    level: Annotated[str, typer.Option("--level", help="Minimum log level.")] = "INFO",
    log_id: Annotated[
        uuid.UUID | None,
        typer.Option("--log-id", help="Filter to a specific CT log UUID."),
    ] = None,
) -> None:
    """Stream application log output to the terminal with Rich formatting."""
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(
        level=numeric_level,
        format="%(asctime)s %(levelname)-8s %(name)s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
    _console.print(
        f"Following logs at level [cyan]{level.upper()}[/cyan]. Press Ctrl-C to stop."
    )
    # Block until interrupted — logging output flows through the root handler.
    try:
        asyncio.run(_block_forever())
    except KeyboardInterrupt:
        pass


async def _block_forever() -> None:
    """Await indefinitely; only keyboard interrupt exits."""
    while True:
        await asyncio.sleep(3600)
