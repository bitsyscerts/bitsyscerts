"""``ctpool logs`` sub-command group.

Sub-commands:
    logs sync   — Fetch the CT log list and upsert log sources.
    logs follow — Stream application log output to the terminal.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Annotated

import typer
from rich.console import Console

_console = Console()


def register(app: typer.Typer) -> None:
    """Add the ``logs`` sub-app to *app*."""
    logs_app = typer.Typer(
        help="Manage and follow CT log source configuration.",
        no_args_is_help=True,
    )
    app.add_typer(logs_app, name="logs")

    @logs_app.command("sync")
    def sync() -> None:
        """Fetch the public CT log list and upsert log source rows."""
        from ctpool._cli_ops_impl import run_sync_logs

        asyncio.run(run_sync_logs(_console))

    @logs_app.command("follow")
    def follow(
        level: Annotated[
            str,
            typer.Option("--level", help="Minimum log level (default: INFO)."),
        ] = "INFO",
        log_id: Annotated[
            str | None,
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
            f"Following logs at level [cyan]{level.upper()}[/cyan]. "
            "Press Ctrl-C to stop."
        )
        from ctpool._cli_ops_impl import block_forever

        try:
            asyncio.run(block_forever())
        except KeyboardInterrupt:
            _console.print("\n[yellow]Stopped.[/yellow]")
