"""Implementation for the prune-for-storage-profile CLI command.

Dispatches metrics, observation, and entry-outcome pruning using retention
windows derived from the active storage profile settings.

Exports:
    run_prune_for_storage_profile — Dispatch all profile-appropriate prune ops.
"""

from __future__ import annotations

import logging

from rich.console import Console

from ctpool.config import get_settings

_logger = logging.getLogger(__name__)


async def run_prune_for_storage_profile(
    *,
    execute: bool = False,
    console: Console,
) -> None:
    """Dispatch all prune operations for the active storage profile.

    Runs prune-metrics, prune-observations, and prune-entry-outcomes using
    retention windows from the current config.  Certificate pruning is omitted
    because it has extra safety checks that must be triggered explicitly via
    ``prune-expired-certs``.

    Args:
        execute: If False (default), dry-run only (no deletions).
        console: Rich console for output.
    """
    from ctpool._cli_prune_entry_outcomes_impl import run_prune_entry_outcomes
    from ctpool._cli_prune_observations_impl import run_prune_observations
    from ctpool._cli_reap_impl import run_prune_metrics

    settings = get_settings()
    mode_label = "execute" if execute else "dry-run"

    console.print(
        f"[bold]prune-for-storage-profile[/bold] | mode={mode_label} | "
        f"profile={settings.ct_storage_profile}"
    )

    await run_prune_metrics(
        dry_run=not execute,
        retention_days=settings.ct_metrics_retention_days,
        console=console,
    )

    await run_prune_observations(
        dry_run=not execute,
        retention_days=settings.ct_observation_retention_days,
        console=console,
    )

    await run_prune_entry_outcomes(
        dry_run=not execute,
        retention_days=settings.ct_entry_outcome_retention_days,
        console=console,
    )

    console.print("[bold green]Prune-for-storage-profile complete.[/bold green]")
