"""Stats CLI commands for ctpool.

Command groups:
    stats          — Display per-log ingestion statistics (live table).
    stats-snapshot — Take a single stats snapshot or run the snapshot loop.
"""

from __future__ import annotations

import asyncio
from typing import Annotated

import typer
from rich.console import Console

_console = Console()


def register(app: typer.Typer) -> None:
    """Register stats commands on *app*."""

    @app.command("stats")
    def stats(
        watch: Annotated[
            bool, typer.Option("--watch", "--live", help="Refresh every 5 seconds.")
        ] = False,
    ) -> None:
        """Display per-log ingestion statistics."""
        from ctpool._cli_ops_impl import run_stats

        asyncio.run(run_stats(watch=watch, console=_console))

    @app.command("stats-snapshot")
    def stats_snapshot(
        loop: Annotated[
            bool,
            typer.Option(
                "--loop", help="Run as a long-lived loop (for Docker services)."
            ),
        ] = False,
    ) -> None:
        """Take a single stats snapshot and write it to ct_stats_snapshots.

        Use ``--loop`` to run as a persistent service that refreshes on the
        ``ct_stats_heavy_refresh_seconds`` interval (default 300 s).
        """
        from ctpool.config import get_settings
        from ctpool.stats_snapshotter import run_snapshot_loop, take_snapshot_once

        settings = get_settings()
        if loop:
            asyncio.run(run_snapshot_loop(settings))
        else:
            asyncio.run(take_snapshot_once(settings))
            _console.print("[green]Snapshot taken.[/green]")
