"""Workers CLI commands for ctpool.

Command groups:
    workers — Inspect and manage worker heartbeat rows.

Sub-commands:
    workers list       — Show all non-stopped worker rows.
    workers reap-stale — Mark stale worker rows as stopped.
"""

from __future__ import annotations

import asyncio
from typing import Annotated

import typer

from ctpool._cli_workers_impl import run_list_workers, run_reap_workers


def register(app: typer.Typer) -> None:
    """Register ``workers`` sub-commands on *app*."""
    workers_app = typer.Typer(help="Inspect and manage worker heartbeat rows.")
    app.add_typer(workers_app, name="workers")

    @workers_app.command("list")
    def list_workers(
        stale_seconds: Annotated[
            int | None,
            typer.Option(
                "--stale-seconds",
                help="Age threshold (default: from settings).",
            ),
        ] = None,
    ) -> None:
        """List all active worker rows from ct_worker_runtime."""
        asyncio.run(run_list_workers(stale_seconds=stale_seconds))

    @workers_app.command("reap-stale")
    def reap_stale(
        stale_seconds: Annotated[
            int | None,
            typer.Option(
                "--stale-seconds",
                help="Age threshold (default: from settings).",
            ),
        ] = None,
        dry_run: Annotated[
            bool,
            typer.Option(
                "--dry-run",
                help="Report stale workers without modifying any rows.",
            ),
        ] = False,
    ) -> None:
        """Mark stale worker rows as stopped in ct_worker_runtime."""
        asyncio.run(run_reap_workers(stale_seconds=stale_seconds, dry_run=dry_run))
