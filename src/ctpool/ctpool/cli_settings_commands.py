"""Storage settings CLI commands backed by the ct_instance_settings table.

Commands:
    profile show   — Show the active database-backed storage profile.
    profile list   — List all built-in profiles with their defaults.
"""

from __future__ import annotations

import asyncio
from typing import Annotated

import typer

_console_lazy: object = None


def _console() -> "Console":  # type: ignore[name-defined]  # noqa: F821
    """Lazy-import rich.Console to avoid module-level heavy imports."""
    global _console_lazy
    if _console_lazy is None:
        from rich.console import Console as _C

        _console_lazy = _C()
    return _console_lazy  # type: ignore[return-value]


profile_app = typer.Typer(
    name="profile",
    help="Manage the active storage profile stored in the database.",
    no_args_is_help=True,
)


@profile_app.command("show")
def show_profile(
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Emit JSON instead of the Rich table."),
    ] = False,
) -> None:
    """Show the active storage profile from the database."""
    import json as _json

    from ctpool.config import get_settings

    settings = get_settings()

    async def _fetch() -> object:
        from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

        engine = create_async_engine(str(settings.database_url), echo=False)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with factory() as session:
            from ctpool.instance_settings import get_active_settings

            row = await get_active_settings(session)
        await engine.dispose()
        return row

    row = asyncio.run(_fetch())
    if row is None:
        typer.echo(
            "No storage profile found in the database. Run the worker to bootstrap.",
            err=True,
        )
        raise typer.Exit(code=1)

    data = {
        "storage_profile": row.storage_profile,  # type: ignore[union-attr]
        "cert_storage_mode": row.cert_storage_mode,  # type: ignore[union-attr]
        "hostname_retention_mode": row.hostname_retention_mode,  # type: ignore[union-attr]
        "backfill_days": row.backfill_days,  # type: ignore[union-attr]
        "cert_retention_days": row.cert_retention_days,  # type: ignore[union-attr]
        "observation_retention_days": row.observation_retention_days,  # type: ignore[union-attr]
        "entry_outcome_retention_days": row.entry_outcome_retention_days,  # type: ignore[union-attr]
        "metrics_retention_days": row.metrics_retention_days,  # type: ignore[union-attr]
        "settings_hash": row.settings_hash,  # type: ignore[union-attr]
        "updated_at": str(row.updated_at),  # type: ignore[union-attr]
        "updated_by": row.updated_by,  # type: ignore[union-attr]
    }
    if json_output:
        typer.echo(_json.dumps(data, indent=2))
        return

    from rich.table import Table

    console = _console()
    table = Table(title="Active Storage Profile", show_header=True)
    table.add_column("Field", style="bold cyan")
    table.add_column("Value")
    for key, value in data.items():
        table.add_row(key, str(value) if value is not None else "—")
    console.print(table)


@profile_app.command("list")
def list_profiles() -> None:
    """List all built-in profiles with their default settings."""
    from rich.table import Table

    from ctpool.profile_defaults import PROFILE_DEFAULTS
    from ctpool.storage_modes import StorageProfile

    console = _console()
    table = Table(title="Built-in Storage Profiles", show_header=True)
    table.add_column("Profile", style="bold")
    table.add_column("Cert Mode")
    table.add_column("Backfill")
    table.add_column("Cert Ret.")
    table.add_column("Obs Ret.")
    table.add_column("Outcome Ret.")
    table.add_column("Metrics Ret.")

    for profile in StorageProfile:
        d = PROFILE_DEFAULTS[profile]
        table.add_row(
            profile.value,
            str(d["cert_storage_mode"]),
            str(d["backfill_days"]),
            str(d["cert_retention_days"]),
            str(d["observation_retention_days"]),
            str(d["entry_outcome_retention_days"]),
            str(d["metrics_retention_days"]),
        )
    console.print(table)
