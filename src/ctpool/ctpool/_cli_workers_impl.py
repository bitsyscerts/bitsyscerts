"""Async implementation helpers for the workers CLI commands.

Extracted to keep cli_workers_commands.py under the 200-line limit.

Exports:
    run_list_workers  — Display active worker rows in a table.
    run_reap_workers  — Reap stale worker heartbeats from ct_worker_runtime.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from rich.console import Console
from rich.table import Table
from sqlalchemy import select, update

from ctpool.config import get_settings
from ctpool.db import create_engine, create_session_factory
from ctpool.models.worker_runtime import CtWorkerRuntime

_STATUS_STOPPED = "stopped"


def _format_age(dt: datetime) -> str:
    """Return a human-readable age string like '4s ago'."""
    delta = datetime.now(UTC) - dt
    total_s = int(delta.total_seconds())
    if total_s < 60:
        return f"{total_s}s ago"
    if total_s < 3600:
        return f"{total_s // 60}m ago"
    return f"{total_s // 3600}h ago"


async def run_list_workers(*, stale_seconds: int | None) -> None:
    """Fetch and display active workers from ct_worker_runtime.

    Args:
        stale_seconds: Threshold for marking a worker as stale. When ``None``
                       the value from application settings is used.
    """
    settings = get_settings()
    effective_stale = (
        stale_seconds if stale_seconds is not None else settings.ct_worker_stale_seconds
    )
    console = Console()

    engine = create_engine(settings)
    session_factory = create_session_factory(engine)
    async with session_factory() as session:
        result = await session.execute(
            select(CtWorkerRuntime)
            .where(CtWorkerRuntime.status != _STATUS_STOPPED)
            .order_by(CtWorkerRuntime.started_at.asc())
        )
        rows = list(result.scalars().all())

    await engine.dispose()

    if not rows:
        console.print("[dim]No active workers.[/dim]")
        return

    cutoff = datetime.now(UTC) - timedelta(seconds=effective_stale)
    table = Table(title=f"Active Workers (stale_seconds={effective_stale})")
    table.add_column("Worker ID", style="cyan")
    table.add_column("Kind", style="magenta")
    table.add_column("Log", style="white", max_width=30, no_wrap=True)
    table.add_column("Status", style="yellow")
    table.add_column("Last Seen")
    table.add_column("Index", justify="right")

    for row in rows:
        is_stale = row.last_heartbeat_at < cutoff
        heartbeat_age = _format_age(row.last_heartbeat_at)
        index_str = f"{row.current_index:,}" if row.current_index is not None else "-"
        status_str = f"[red]{row.status}[/red]" if is_stale else row.status
        table.add_row(
            row.worker_id,
            row.worker_kind,
            row.log_name or "-",
            status_str,
            f"[red]{heartbeat_age}[/red]" if is_stale else heartbeat_age,
            index_str,
        )

    console.print(table)


async def run_reap_workers(*, stale_seconds: int | None, dry_run: bool) -> None:
    """Reset ct_worker_runtime rows whose heartbeat has expired.

    Args:
        stale_seconds: Threshold in seconds. When ``None`` uses settings default.
        dry_run:       When ``True`` report without modifying any rows.
    """
    settings = get_settings()
    effective_stale = (
        stale_seconds if stale_seconds is not None else settings.ct_worker_stale_seconds
    )
    console = Console()

    cutoff = datetime.now(UTC) - timedelta(seconds=effective_stale)

    engine = create_engine(settings)
    session_factory = create_session_factory(engine)
    async with session_factory() as session:
        stale_stmt = (
            select(CtWorkerRuntime.id, CtWorkerRuntime.worker_id)
            .where(CtWorkerRuntime.status != _STATUS_STOPPED)
            .where(CtWorkerRuntime.last_heartbeat_at < cutoff)
        )
        result = await session.execute(stale_stmt)
        stale_rows = result.all()

        if not stale_rows:
            console.print(
                "[green]No stale worker rows found "
                f"(threshold={effective_stale}s).[/green]"
            )
            await engine.dispose()
            return

        if dry_run:
            console.print(
                f"[yellow]Would reap {len(stale_rows)} stale worker row(s) "
                f"(threshold={effective_stale}s):[/yellow]"
            )
            for row in stale_rows:
                console.print(f"  worker_id={row.worker_id}")
            await engine.dispose()
            return

        stale_ids: list[uuid.UUID] = [r.id for r in stale_rows]
        now = datetime.now(UTC)
        async with session.begin():
            await session.execute(
                update(CtWorkerRuntime)
                .where(CtWorkerRuntime.id.in_(stale_ids))
                .values(status=_STATUS_STOPPED, stopped_at=now, updated_at=now)
            )

    await engine.dispose()
    console.print(
        f"[green]Reaped {len(stale_rows)} stale worker row(s) "
        f"(threshold={effective_stale}s).[/green]"
    )
