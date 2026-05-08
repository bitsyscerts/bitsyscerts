"""Prune (data retention) CLI commands.

Commands:
    prune-metrics           — Delete old ingestion_metrics rows.
    prune-expired-certs     — Prune expired certificate rows safely.
    prune-observations      — Delete old ct_log_observations rows.
    prune-entry-outcomes    — Delete old ct_entry_outcomes rows.
    prune-for-storage-profile — Dispatch all pruning for the active profile.
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
        dry_run: Annotated[
            bool,
            typer.Option(
                "--dry-run",
                help="Count candidates without deleting.",
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

        Only certificates that are not the latest cert for any hostname are removed.
        Pass --dry-run to count candidates without deleting.
        """
        from ctpool._cli_prune_impl import run_prune_expired_certs

        asyncio.run(
            run_prune_expired_certs(
                execute=not dry_run,
                retention_days=retention_days,
                batch_size=batch_size,
                limit=limit,
                console=_console,
            )
        )

    @app.command("prune-observations")
    def prune_observations(
        dry_run: Annotated[
            bool,
            typer.Option("--dry-run", help="Count rows that would be deleted."),
        ] = False,
        retention_days: Annotated[
            int | None,
            typer.Option(
                "--retention-days",
                help="Override ct_observation_retention_days from config.",
            ),
        ] = None,
        batch_size: Annotated[
            int,
            typer.Option("--batch-size", help="Rows to delete per transaction."),
        ] = 5000,
        limit: Annotated[
            int,
            typer.Option("--limit", help="Maximum rows to delete (0 = unlimited)."),
        ] = 0,
    ) -> None:
        """Delete old ct_log_observations rows beyond the retention window.

        Pass --dry-run to count candidates without deleting.
        """
        from ctpool._cli_prune_observations_impl import run_prune_observations

        asyncio.run(
            run_prune_observations(
                dry_run=dry_run,
                retention_days=retention_days,
                batch_size=batch_size,
                limit=limit,
                console=_console,
            )
        )

    @app.command("prune-entry-outcomes")
    def prune_entry_outcomes(
        dry_run: Annotated[
            bool,
            typer.Option("--dry-run", help="Count rows that would be deleted."),
        ] = False,
        retention_days: Annotated[
            int | None,
            typer.Option(
                "--retention-days",
                help="Override ct_entry_outcome_retention_days from config.",
            ),
        ] = None,
        batch_size: Annotated[
            int,
            typer.Option("--batch-size", help="Rows to delete per transaction."),
        ] = 5000,
        limit: Annotated[
            int,
            typer.Option("--limit", help="Maximum rows to delete (0 = unlimited)."),
        ] = 0,
    ) -> None:
        """Delete old ct_entry_outcomes rows beyond the retention window.

        Pass --dry-run to count candidates without deleting.
        """
        from ctpool._cli_prune_entry_outcomes_impl import run_prune_entry_outcomes

        asyncio.run(
            run_prune_entry_outcomes(
                dry_run=dry_run,
                retention_days=retention_days,
                batch_size=batch_size,
                limit=limit,
                console=_console,
            )
        )

    @app.command("prune-for-storage-profile")
    def prune_for_storage_profile(
        dry_run: Annotated[
            bool,
            typer.Option("--dry-run", help="Count rows that would be deleted."),
        ] = False,
    ) -> None:
        """Run all prune operations appropriate for the active storage profile.

        Dispatches: prune-metrics, prune-observations, prune-entry-outcomes.
        Certificate pruning is not included here — use prune-expired-certs
        separately as it has additional safety checks.

        Pass --dry-run to count candidates without deleting.
        """
        from ctpool._cli_prune_storage_profile_impl import (
            run_prune_for_storage_profile,
        )

        asyncio.run(
            run_prune_for_storage_profile(execute=not dry_run, console=_console)
        )
