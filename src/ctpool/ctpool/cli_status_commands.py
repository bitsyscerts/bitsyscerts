"""``ctpool status`` — concise operator summary read from the latest snapshot.

This file owns the Typer registration only; the actual rendering lives
in :mod:`ctpool._cli_status_impl` so it can be unit tested in isolation
without needing a Typer runner.
"""

from __future__ import annotations

import asyncio

import typer
from rich.console import Console

_console = Console()


def register(app: typer.Typer) -> None:
    """Register the ``status`` command on *app*."""

    @app.command("status")
    def status() -> None:
        """Show a concise operator summary from the latest stats snapshot.

        Reads from the cached snapshot only — never runs heavy live
        queries.  When no snapshot exists, prints a clear message
        instructing the operator to run ``ctpool stats-snapshot --once``.
        """
        from ctpool._cli_status_impl import run_status
        from ctpool.config import get_settings

        settings = get_settings()
        threshold = int(getattr(settings, "stats_stale_seconds", 120))
        asyncio.run(
            run_status(
                settings=settings,
                stale_threshold_seconds=threshold,
                console=_console,
            )
        )
