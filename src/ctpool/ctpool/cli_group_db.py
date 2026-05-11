"""``ctpool db`` sub-command group.

Thin wrappers around existing DB-management implementations.

Sub-commands:
    db migrate — Apply Alembic migrations (idempotent).
    db init    — Create DB schema from scratch.
    db status  — Show schema revision and connectivity.
"""

from __future__ import annotations

import asyncio

import typer
from rich.console import Console

_console = Console()


def register(app: typer.Typer) -> None:
    """Add the ``db`` sub-app to *app*."""
    db_app = typer.Typer(
        help="Database initialization, migrations, and status.",
        no_args_is_help=True,
    )
    app.add_typer(db_app, name="db")

    @db_app.command("migrate")
    def migrate() -> None:
        """Apply Alembic migrations to head and ensure instance settings."""
        from ctpool.bootstrap_config import get_bootstrap_config
        from ctpool.config import get_settings
        from ctpool.db import create_engine, create_session_factory, get_session
        from ctpool.instance_settings import bootstrap_settings_from_env
        from ctpool.migration_runner import run_upgrade_head

        settings = get_settings()

        async def _run() -> str:
            await run_upgrade_head(settings)
            engine = create_engine(settings)
            try:
                factory = create_session_factory(engine)
                async with get_session(factory) as session:
                    row = await bootstrap_settings_from_env(
                        session, get_bootstrap_config()
                    )
                return row.storage_profile
            finally:
                await engine.dispose()

        try:
            profile = asyncio.run(_run())
        except Exception as exc:  # noqa: BLE001
            _console.print(f"[red]Migration failed: {exc}[/red]")
            raise typer.Exit(code=1) from exc
        _console.print("[green]Database schema is up to date.[/green]")
        _console.print(f"[green]Active storage profile: {profile}[/green]")

    @db_app.command("init")
    def init() -> None:
        """Create or update the database schema (safe, no data loss)."""
        from ctpool.config import get_settings
        from ctpool.database_init import run_init_db
        from ctpool.exceptions import DatabaseInitError

        settings = get_settings()
        try:
            asyncio.run(run_init_db(settings, force=False))
        except DatabaseInitError as exc:
            _console.print(f"[red]DB init failed: {exc}[/red]")
            raise typer.Exit(code=1) from exc
        _console.print("[green]Database schema is up to date.[/green]")

    @db_app.command("status")
    def db_status() -> None:
        """Show the current Alembic revision and database connectivity."""
        from ctpool.config import get_settings
        from ctpool.migration_runner import (
            get_current_revision,
            get_missing_core_tables,
        )

        settings = get_settings()

        async def _run() -> None:
            revision = await get_current_revision(settings)
            if revision is None:
                _console.print(
                    "[yellow]No migrations applied (schema not initialised).[/yellow]"
                )
                return
            _console.print(f"Current revision: [cyan]{revision}[/cyan]")
            missing = await get_missing_core_tables(settings)
            if missing:
                _console.print(
                    "[red]Schema is incomplete; missing tables:[/red] "
                    f"[cyan]{', '.join(missing)}[/cyan]"
                )
            else:
                _console.print(
                    "[green]Schema is complete — all core tables present.[/green]"
                )

        asyncio.run(_run())
