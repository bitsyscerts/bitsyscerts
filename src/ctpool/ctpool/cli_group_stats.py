"""``ctpool stats`` sub-command group.

Sub-commands:
    stats show     — Display the latest stats snapshot.
    stats snapshot — Capture a fresh stats snapshot (once or on a loop).
"""

from __future__ import annotations

import asyncio
from typing import Annotated

import typer
from rich.console import Console

_console = Console()


def register(app: typer.Typer) -> None:
    """Add the ``stats`` sub-app to *app*."""
    stats_app = typer.Typer(
        help="View and capture CT pool statistics.",
        no_args_is_help=True,
    )
    app.add_typer(stats_app, name="stats")

    @stats_app.command("show")
    def show() -> None:
        """Display per-log ingestion statistics (reads live from database)."""
        from ctpool._cli_ops_impl import run_stats

        asyncio.run(run_stats(watch=False, console=_console))

    @stats_app.command("snapshot")
    def snapshot(
        once: Annotated[
            bool,
            typer.Option("--once", help="Capture one snapshot then exit."),
        ] = False,
        loop: Annotated[
            bool,
            typer.Option("--loop", help="Capture snapshots on a schedule."),
        ] = False,
    ) -> None:
        """Capture a stats snapshot and persist it to the database."""
        from ctpool.config import get_settings
        from ctpool.stats_snapshotter import (
            run_snapshot_loop,
            take_snapshot_once,
        )

        settings = get_settings()
        if loop:
            asyncio.run(run_snapshot_loop(settings, console=_console))
        else:
            asyncio.run(take_snapshot_once(settings))
            _console.print("[green]Snapshot captured.[/green]")
