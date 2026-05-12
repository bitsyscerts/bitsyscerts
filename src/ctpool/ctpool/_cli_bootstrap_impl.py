"""Bootstrap implementation — idempotent first-run / re-run helper.

All steps are safe to run more than once.  No long-running workers are
started.  No databases are destroyed.

Steps:
    1. Apply database migrations.
    2. Ensure the instance settings row exists.
    3. Sync CT log sources from the public log list (soft-fail).
    4. Take a single stats snapshot (soft-fail).
    5. Run one maintenance pass (soft-fail).
    6. Print the operator status summary.
"""

from __future__ import annotations

from rich.console import Console

from ctpool._cli_ops_impl import run_sync_logs
from ctpool._cli_status_impl import run_status
from ctpool.bootstrap_config import get_bootstrap_config
from ctpool.config import Settings
from ctpool.db import create_engine, create_session_factory, get_session
from ctpool.instance_settings import bootstrap_settings_from_env
from ctpool.maintenance_runner import run_maintenance_once
from ctpool.migration_runner import run_upgrade_head
from ctpool.stats_snapshotter import take_snapshot_once


async def run_bootstrap(*, settings: Settings, console: Console) -> None:
    """Run the six-step bootstrap sequence.

    All steps are idempotent.  Steps 3–5 are soft-fail: a warning is
    printed and the sequence continues if they error.  Steps 1 and 2
    are hard-fail: they raise immediately so the operator can diagnose
    the problem.

    Args:
        settings: ``ctpool`` runtime settings.
        console:  Rich console for user-visible output.
    """
    await _step_migrate(settings, console)
    await _step_ensure_settings(settings, console)
    await _step_sync_logs(console)
    await _step_snapshot(settings, console)
    await _step_maintenance(settings, console)
    await _step_status(settings, console)
    _print_next_steps(console)


async def _step_migrate(settings: Settings, console: Console) -> None:
    """Apply Alembic migrations to head."""
    console.print("[cyan]Step 1/6:[/cyan] Applying database migrations…")
    await run_upgrade_head(settings)
    console.print("[green]  ✓ Migrations applied.[/green]")


async def _step_ensure_settings(settings: Settings, console: Console) -> None:
    """Create the instance settings row if it does not exist."""
    console.print("[cyan]Step 2/6:[/cyan] Ensuring instance settings row…")
    engine = create_engine(settings)
    try:
        factory = create_session_factory(engine)
        async with get_session(factory) as session:
            row = await bootstrap_settings_from_env(session, get_bootstrap_config())
        console.print(
            f"[green]  ✓ Active storage profile: {row.storage_profile}[/green]"
        )
    finally:
        await engine.dispose()


async def _step_sync_logs(console: Console) -> None:
    """Fetch the CT log list and upsert log sources (soft-fail)."""
    console.print("[cyan]Step 3/6:[/cyan] Syncing CT log sources…")
    try:
        await run_sync_logs(console)
        console.print("[green]  ✓ CT logs synced.[/green]")
    except Exception as exc:  # noqa: BLE001
        console.print(f"[yellow]  ⚠ Log sync warning (non-fatal): {exc}[/yellow]")
        console.print("[yellow]  Run 'ctpool logs sync' later to retry.[/yellow]")


async def _step_snapshot(settings: Settings, console: Console) -> None:
    """Take one stats snapshot (soft-fail)."""
    console.print("[cyan]Step 4/6:[/cyan] Taking stats snapshot…")
    try:
        await take_snapshot_once(settings)
        console.print("[green]  ✓ Snapshot taken.[/green]")
    except Exception as exc:  # noqa: BLE001
        console.print(f"[yellow]  ⚠ Snapshot warning (non-fatal): {exc}[/yellow]")


async def _step_maintenance(settings: Settings, console: Console) -> None:
    """Run one maintenance pass (soft-fail)."""
    console.print("[cyan]Step 5/6:[/cyan] Running maintenance pass…")
    try:
        await run_maintenance_once(settings)
        console.print("[green]  ✓ Maintenance pass complete.[/green]")
    except Exception as exc:  # noqa: BLE001
        console.print(f"[yellow]  ⚠ Maintenance warning (non-fatal): {exc}[/yellow]")


async def _step_status(settings: Settings, console: Console) -> None:
    """Print the operator status summary."""
    console.print("[cyan]Step 6/6:[/cyan] Operator status summary:")
    await run_status(
        settings=settings,
        stale_threshold_seconds=300,
        console=console,
    )


def _print_next_steps(console: Console) -> None:
    """Print next-step guidance for starting workers."""
    console.rule("[bold]Bootstrap complete[/bold]")
    console.print("[bold]Start workers:[/bold]")
    console.print("  ctpool worker tail")
    console.print("  ctpool worker backfill")
    console.print("")
    console.print("[bold]Or with Docker Compose:[/bold]")
    console.print("  docker compose up -d")
