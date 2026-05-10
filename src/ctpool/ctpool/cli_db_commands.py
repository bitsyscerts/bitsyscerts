"""Database management CLI commands.

Commands:
    apply-migrations — Run Alembic migrations to head (idempotent).
    db-init          — Deprecated alias for apply-migrations.
    init-db          — Create or forcibly recreate the DB, then migrate.
    db-status        — Show current schema revision and DB connectivity.
"""

from __future__ import annotations

import asyncio
from typing import Annotated

import typer
from rich.console import Console

from ctpool.config import Settings
from ctpool.exceptions import DatabaseInitError, SchemaStateError

_console = Console()


async def _ensure_bootstrap_settings(settings: Settings) -> str:
    """Create the initial instance settings row if it does not yet exist."""
    from ctpool.bootstrap_config import get_bootstrap_config
    from ctpool.db import create_engine, create_session_factory, get_session
    from ctpool.instance_settings import bootstrap_settings_from_env

    engine = create_engine(settings)
    try:
        session_factory = create_session_factory(engine)
        async with get_session(session_factory) as session:
            row = await bootstrap_settings_from_env(session, get_bootstrap_config())
        return row.storage_profile
    finally:
        await engine.dispose()


async def _migrate_and_bootstrap(settings: Settings) -> str:
    """Apply migrations and ensure the first runtime settings row exists."""
    from ctpool.migration_runner import run_upgrade_head

    await run_upgrade_head(settings)
    return await _ensure_bootstrap_settings(settings)


def register(app: typer.Typer) -> None:
    """Register all DB management commands on *app*."""

    def _apply_migrations() -> None:
        from ctpool.config import get_settings

        settings = get_settings()
        try:
            profile = asyncio.run(_migrate_and_bootstrap(settings))
        except SchemaStateError as exc:
            _console.print(f"[red]{exc}[/red]")
            raise typer.Exit(code=1) from exc
        _console.print("[green]Database schema is up to date.[/green]")
        _console.print(f"[green]Active storage profile: {profile}.[/green]")

    @app.command("apply-migrations")
    def apply_migrations() -> None:
        """Run Alembic migrations to head (idempotent)."""
        _apply_migrations()

    @app.command("db-init", hidden=True)
    def db_init() -> None:
        """Run Alembic migrations to head via the deprecated db-init alias."""
        _apply_migrations()

    @app.command("init-db")
    def init_db(
        force: Annotated[
            bool,
            typer.Option(
                "--force",
                help=(
                    "Drop and recreate the target database before applying migrations."
                ),
            ),
        ] = False,
    ) -> None:
        """Create or forcibly recreate the target DB, then apply migrations."""
        from ctpool.config import get_settings
        from ctpool.database_init import run_init_db

        settings = get_settings()
        try:
            action = asyncio.run(run_init_db(settings, force=force))
            profile = asyncio.run(_ensure_bootstrap_settings(settings))
        except DatabaseInitError as exc:
            _console.print(f"[red]{exc}[/red]")
            raise typer.Exit(code=1) from exc
        if action == "created":
            _console.print("[green]Database created and migrated.[/green]")
            _console.print(f"[green]Active storage profile: {profile}.[/green]")
            return
        if action == "recreated":
            _console.print("[green]Database recreated and migrated.[/green]")
            _console.print(f"[green]Active storage profile: {profile}.[/green]")
            return
        _console.print("[green]Database schema is up to date.[/green]")
        _console.print(f"[green]Active storage profile: {profile}.[/green]")

    @app.command("db-status")
    def db_status() -> None:
        """Show the current Alembic revision and DB connectivity."""
        from ctpool.config import get_settings
        from ctpool.migration_runner import (
            get_current_revision,
            get_missing_core_tables,
        )

        settings = get_settings()
        revision = asyncio.run(get_current_revision(settings))
        if revision is None:
            _console.print(
                "[yellow]No migrations applied (schema not initialised).[/yellow]"
            )
        else:
            _console.print(f"Current revision: [cyan]{revision}[/cyan]")
            missing_tables = asyncio.run(get_missing_core_tables(settings))
            if missing_tables:
                _console.print(
                    "[red]Schema is incomplete; missing tables:[/red] "
                    f"[cyan]{', '.join(missing_tables)}[/cyan]"
                )
