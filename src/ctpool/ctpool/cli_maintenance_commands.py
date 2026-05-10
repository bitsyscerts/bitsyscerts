"""Maintenance CLI commands for ctpool.

Command groups:
    maintenance — Run maintenance tasks once or as a persistent loop.
"""

from __future__ import annotations

import asyncio
from typing import Annotated

import typer
from rich.console import Console

_console = Console()


def register(app: typer.Typer) -> None:
    """Register maintenance commands on *app*."""

    @app.command("maintenance")
    def maintenance(
        loop: Annotated[
            bool,
            typer.Option(
                "--loop",
                help="Run as a long-lived loop (for Docker services).",
            ),
        ] = False,
    ) -> None:
        """Run lightweight profile-aware maintenance.

        By default this runs ``prune-for-storage-profile`` only.  Deep
        ``check-audit-gaps`` scans are **disabled unless**
        ``BITSYSCERTS_ENABLE_SCHEDULED_AUDIT=true``; when enabled they run
        on ``BITSYSCERTS_AUDIT_INTERVAL_SECONDS`` and never block prune.

        Use ``--loop`` to run as a persistent service that repeats on the
        ``ct_maintenance_interval_seconds`` interval (default 3600 s).
        """
        from ctpool.config import get_settings
        from ctpool.maintenance_runner import run_maintenance_loop, run_maintenance_once

        settings = get_settings()
        if loop:
            asyncio.run(run_maintenance_loop(settings))
        else:
            asyncio.run(run_maintenance_once(settings))
            _console.print("[green]Maintenance run complete.[/green]")
