"""Prune (data retention) CLI commands.

Commands:
    prune-metrics        — Delete old ingestion_metrics rows.
    prune-expired-certs  — Prune expired certificate rows safely.
"""

from __future__ import annotations

import asyncio
from typing import Annotated

import typer
from rich.console import Console

_console = Console()


def register(app: typer.Typer) -> None:
    """Register all prune / retention commands on *app*."""

    @app.command("prune-metrics")
    def prune_metrics(
        dry_run: Annotated[
            bool,
            typer.Option("--dry-run", help="Count rows that would be deleted."),
        ] = False,
        retention_days: Annotated[
            int | None,
            typer.Option(
                "--retention-days",
                help="Override ct_metrics_retention_days from config.",
            ),
        ] = None,
    ) -> None:
        """Delete old ingestion_metrics rows to free up database space."""
        from ctpool._cli_reap_impl import run_prune_metrics

        asyncio.run(
            run_prune_metrics(
                dry_run=dry_run,
                retention_days=retention_days,
                console=_console,
            )
        )

    @app.command("prune-expired-certs")
    def prune_expired_certs(
        execute: Annotated[
            bool,
            typer.Option(
                "--execute",
                help="Execute deletions (default is dry-run).",
            ),
        ] = False,
        retention_days: Annotated[
            int | None,
            typer.Option(
                "--retention-days",
                help="Override ct_expired_cert_retention_days from config.",
            ),
        ] = None,
        batch_size: Annotated[
            int,
            typer.Option(
                "--batch-size", help="Certificates to delete per transaction."
            ),
        ] = 500,
        limit: Annotated[
            int,
            typer.Option("--limit", help="Maximum certs to delete (0 = unlimited)."),
        ] = 0,
    ) -> None:
        """Prune expired certificate rows not referenced as a hostname's latest cert.

        Runs in dry-run mode by default. Pass --execute to perform deletions.
        Only certificates that are not the latest cert for any hostname are removed.
        """
        from ctpool._cli_prune_impl import run_prune_expired_certs

        asyncio.run(
            run_prune_expired_certs(
                execute=execute,
                retention_days=retention_days,
                batch_size=batch_size,
                limit=limit,
                console=_console,
            )
        )
