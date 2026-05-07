"""Storage profile CLI commands.

Commands:
    storage-profile — Show the active storage profile and per-mode projections.
"""

from __future__ import annotations

from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

_console = Console()


def register(app: typer.Typer) -> None:
    """Register storage profile commands on *app*."""

    @app.command("storage-profile")
    def storage_profile(
        json_output: Annotated[
            bool,
            typer.Option("--json", help="Emit JSON instead of the Rich table."),
        ] = False,
    ) -> None:
        """Show the active storage profile, cert storage mode, and projections."""
        import json

        from ctpool.config import get_settings
        from ctpool.profile_projection import (
            bytes_per_observation_range,
        )
        from ctpool.storage_modes import resolve_profile_defaults

        settings = get_settings()
        profile, cert_mode = resolve_profile_defaults(
            settings.ct_storage_profile,
            settings.ct_cert_storage_mode or None,
        )

        if json_output:
            low, high = bytes_per_observation_range(cert_mode)
            payload = {
                "storage_profile": profile.value,
                "cert_storage_mode": cert_mode.value,
                "hostname_retention_mode": settings.ct_hostname_retention_mode,
                "cert_retention_days": settings.ct_cert_retention_days,
                "observation_retention_days": settings.ct_observation_retention_days,
                "entry_outcome_retention_days": (
                    settings.ct_entry_outcome_retention_days
                ),
                "bytes_per_observation_low": low,
                "bytes_per_observation_high": high,
            }
            print(json.dumps(payload, indent=2))
            return

        t = Table(title="Active Storage Profile", show_lines=False)
        t.add_column("Setting", style="bold")
        t.add_column("Value")
        t.add_row("Profile", profile.value)
        t.add_row("Cert storage mode", cert_mode.value)
        t.add_row("Hostname retention", settings.ct_hostname_retention_mode)
        t.add_row("Cert retention days", str(settings.ct_cert_retention_days))
        t.add_row(
            "Observation retention days", str(settings.ct_observation_retention_days)
        )
        t.add_row(
            "Entry outcome retention days",
            str(settings.ct_entry_outcome_retention_days),
        )

        low, high = bytes_per_observation_range(cert_mode)
        t.add_row(
            "Bytes/observation (est.)",
            f"{low:,} – {high:,}",
        )
        _console.print(t)
