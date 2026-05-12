"""``ctpool maintenance`` sub-command group.

Sub-commands:
    maintenance run  — Run one maintenance pass then exit.
    maintenance loop — Run maintenance on a recurring schedule.
"""

from __future__ import annotations

import asyncio

import typer
from rich.console import Console

_console = Console()


def register(app: typer.Typer) -> None:
    """Add the ``maintenance`` sub-app to *app*."""
    maintenance_app = typer.Typer(
        help="Run the scheduled maintenance and retention pipeline.",
        no_args_is_help=True,
    )
    app.add_typer(maintenance_app, name="maintenance")

    @maintenance_app.command("run")
    def run() -> None:
        """Run one maintenance pass (prune, vacuum, compaction) then exit."""
        from ctpool.config import get_settings
        from ctpool.maintenance_runner import run_maintenance_once

        settings = get_settings()
        asyncio.run(run_maintenance_once(settings))
        _console.print("[green]Maintenance pass complete.[/green]")

    @maintenance_app.command("loop")
    def loop() -> None:
        """Run maintenance on a recurring schedule until interrupted."""
        from ctpool.config import get_settings
        from ctpool.maintenance_runner import run_maintenance_loop

        settings = get_settings()
        try:
            asyncio.run(run_maintenance_loop(settings))
        except KeyboardInterrupt:
            _console.print("\n[yellow]Maintenance loop stopped.[/yellow]")
