"""``ctpool storage`` sub-command group.

Sub-commands:
    storage profile — Show or set the active storage profile.
    storage prune   — Dispatch all retention pruning for the active profile.
"""

from __future__ import annotations

import asyncio
from typing import Annotated

import typer
from rich.console import Console

_console = Console()


def register(app: typer.Typer) -> None:
    """Add the ``storage`` sub-app to *app*."""
    storage_app = typer.Typer(
        help="Inspect and manage storage profiles and retention.",
        no_args_is_help=True,
    )
    app.add_typer(storage_app, name="storage")

    @storage_app.command("profile")
    def profile(
        json: Annotated[
            bool,
            typer.Option("--json", help="Emit machine-readable JSON output."),
        ] = False,
    ) -> None:
        """Show the active storage profile and effective retention settings."""
        import json as _json

        from rich.table import Table

        from ctpool.config import get_settings
        from ctpool.profile_projection import bytes_per_observation_range
        from ctpool.storage_modes import resolve_profile_defaults

        settings = get_settings()
        profile_val, cert_mode = resolve_profile_defaults(
            settings.ct_storage_profile,
            settings.ct_cert_storage_mode or None,
        )
        if json:
            low, high = bytes_per_observation_range(cert_mode)
            payload = {
                "storage_profile": profile_val.value,
                "cert_storage_mode": cert_mode.value,
                "hostname_retention_mode": (settings.ct_hostname_retention_mode),
                "cert_retention_days": settings.ct_cert_retention_days,
                "observation_retention_days": (settings.ct_observation_retention_days),
                "entry_outcome_retention_days": (
                    settings.ct_entry_outcome_retention_days
                ),
                "bytes_per_observation_low": low,
                "bytes_per_observation_high": high,
            }
            print(_json.dumps(payload, indent=2))
            return
        t = Table(title="Active Storage Profile", show_lines=False)
        t.add_column("Setting", style="bold")
        t.add_column("Value")
        t.add_row("Profile", profile_val.value)
        t.add_row("Cert storage mode", cert_mode.value)
        t.add_row("Hostname retention", settings.ct_hostname_retention_mode)
        t.add_row("Cert retention days", str(settings.ct_cert_retention_days))
        t.add_row(
            "Observation retention days",
            str(settings.ct_observation_retention_days),
        )
        t.add_row(
            "Entry outcome retention days",
            str(settings.ct_entry_outcome_retention_days),
        )
        low, high = bytes_per_observation_range(cert_mode)
        t.add_row("Bytes/observation (est.)", f"{low:,} \u2013 {high:,}")
        _console.print(t)

    @storage_app.command("prune")
    def prune(
        dry_run: Annotated[
            bool,
            typer.Option(
                "--dry-run",
                help="Report what would be pruned without deleting.",
            ),
        ] = True,
    ) -> None:
        """Dispatch all retention pruning jobs for the active storage profile."""
        from ctpool._cli_prune_storage_profile_impl import (
            run_prune_for_storage_profile,
        )

        asyncio.run(
            run_prune_for_storage_profile(
                execute=not dry_run,
                console=_console,
            )
        )
