"""Legacy range-based dispatch CLI commands.

Subcommands of ``ctpool legacy-ranges`` provide read-only inspection and a
safe dry-run cleanup path for the deprecated ``ct_log_backfill_ranges``
table. Per-log dispatch (``ct_log_backfill_state``) is the primary runtime
in this version; these commands exist only for compatibility, debug, and
intentional cleanup of stale legacy rows.

Commands:
    legacy-ranges status          — Show legacy range status counts.
    legacy-ranges clear --dry-run — Report how many rows would be deleted.
"""

from __future__ import annotations

import asyncio
from typing import Annotated

import typer
from rich.console import Console
from sqlalchemy import delete, func, select

from ctpool.config import Settings
from ctpool.db import create_engine, create_session_factory
from ctpool.models.log_backfill_range import CtLogBackfillRange

_console = Console()


legacy_app = typer.Typer(
    name="legacy-ranges",
    no_args_is_help=True,
    add_completion=False,
    help=(
        "[advanced/debug] Inspect or clear legacy ct_log_backfill_ranges "
        "rows. Per-log dispatch is the active runtime; these commands are "
        "for compatibility and intentional cleanup only."
    ),
)


async def _query_status_counts() -> dict[str, int]:
    settings = Settings()  # type: ignore[call-arg]
    engine = create_engine(settings)
    factory = create_session_factory(engine)
    try:
        async with factory() as session:
            stmt = select(
                CtLogBackfillRange.status,
                func.count().label("n"),
            ).group_by(CtLogBackfillRange.status)
            result = await session.execute(stmt)
            return {row.status: int(row.n) for row in result.all()}
    finally:
        await engine.dispose()


async def _execute_clear(*, dry_run: bool) -> int:
    settings = Settings()  # type: ignore[call-arg]
    engine = create_engine(settings)
    factory = create_session_factory(engine)
    try:
        async with factory() as session:
            count_row = await session.execute(
                select(func.count()).select_from(CtLogBackfillRange)
            )
            total = int(count_row.scalar_one())
            if dry_run or total == 0:
                return total
            async with session.begin():
                await session.execute(delete(CtLogBackfillRange))
            return total
    finally:
        await engine.dispose()


@legacy_app.command("status")
def legacy_status() -> None:
    """[advanced/debug] Show legacy ct_log_backfill_ranges status counts."""
    counts = asyncio.run(_query_status_counts())
    if not counts:
        _console.print("[dim]No legacy range rows present.[/dim]")
        return
    _console.print("[bold]Legacy ct_log_backfill_ranges status counts:[/bold]")
    for status, n in sorted(counts.items()):
        _console.print(f"  {status}: {n}")
    _console.print(
        "[dim]Per-log dispatch is the active runtime. "
        "Use `ctpool backfill-state` for current health.[/dim]"
    )


@legacy_app.command("clear")
def legacy_clear(
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run/--execute",
            help=(
                "Default --dry-run: report how many rows would be deleted "
                "without modifying any data. Use --execute to actually "
                "delete; this requires explicit intent."
            ),
        ),
    ] = True,
) -> None:
    """[advanced/debug] Clear legacy ct_log_backfill_ranges rows.

    Defaults to --dry-run. Pass --execute to actually delete the rows.
    Deletion is irreversible; per-log dispatch state in
    ``ct_log_backfill_state`` is unaffected.
    """
    total = asyncio.run(_execute_clear(dry_run=dry_run))
    if total == 0:
        _console.print("[dim]No legacy range rows present.[/dim]")
        return
    if dry_run:
        _console.print(
            f"[yellow]DRY RUN[/yellow]: would delete {total} legacy range row(s). "
            "Pass --execute to apply."
        )
        return
    _console.print(f"[green]Deleted {total} legacy range row(s).[/green]")


def register(app: typer.Typer) -> None:
    """Register the legacy-ranges command group on *app*."""
    app.add_typer(legacy_app)
