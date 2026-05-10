"""Async implementation helpers for the workers CLI commands.

Extracted to keep cli_workers_commands.py under the 200-line limit.

Exports:
    run_list_workers  — Display active worker rows in a table.
    run_reap_workers  — Reap stale worker heartbeats from ct_worker_runtime.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from rich.console import Console
from rich.table import Table
from sqlalchemy import select

from ctpool.config import get_settings
from ctpool.db import create_engine, create_session_factory
from ctpool.models.worker_runtime import CtWorkerRuntime
from ctpool.worker_queries import query_worker_summary
from ctpool.worker_reaper import reap_stale_worker_rows

_STATUS_STOPPED = "stopped"


def _format_age(total_s: int) -> str:
    """Return a human-readable age string like '4s ago'."""
    if total_s < 60:
        return f"{total_s}s ago"
    if total_s < 3600:
        return f"{total_s // 60}m ago"
    return f"{total_s // 3600}h ago"


def _format_status(item: dict[str, object]) -> str:
    status = str(item["status"])
    if bool(item["is_stale"]):
        return f"[red]{status} (stale)[/red]"
    if status == "processing":
        return f"[green]{status}[/green]"
    if status == "retrying":
        return f"[yellow]{status}[/yellow]"
    if status == "error":
        return f"[red]{status}[/red]"
    if status == "idle":
        return f"[cyan]{status}[/cyan]"
    return status


def _format_log(item: dict[str, object]) -> str:
    log_name = item.get("log_name")
    log_operator = item.get("log_operator")
    if isinstance(log_name, str) and log_name:
        if isinstance(log_operator, str) and log_operator:
            return f"{log_name} ({log_operator})"
        return log_name
    log_source_id = item.get("log_source_id")
    return str(log_source_id) if log_source_id else "-"


def _format_work(item: dict[str, object]) -> str:
    batch_start = item.get("batch_start_index")
    batch_end = item.get("batch_end_index")
    current_index = item.get("current_index")
    checkpoint_index = item.get("checkpoint_index")
    parts: list[str] = []
    if isinstance(item.get("direction"), str) and item["direction"]:
        parts.append(str(item["direction"]))
    if isinstance(batch_start, int) and isinstance(batch_end, int):
        parts.append(f"{batch_start:,}-{batch_end:,}")
    elif isinstance(current_index, int):
        parts.append(f"idx {current_index:,}")
    if isinstance(checkpoint_index, int) and checkpoint_index != current_index:
        parts.append(f"ckpt {checkpoint_index:,}")
    return " | ".join(parts) if parts else "-"


def _format_error(item: dict[str, object]) -> str:
    error_type = item.get("last_error_type")
    error_message = item.get("last_error_message")
    if isinstance(error_type, str) and error_type:
        if isinstance(error_message, str) and error_message:
            return f"{error_type}: {error_message}"
        return error_type
    rate_limited_until = item.get("rate_limited_until")
    if isinstance(rate_limited_until, str) and rate_limited_until:
        return f"retry until {rate_limited_until}"
    return "-"


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
        summary = await query_worker_summary(
            session,
            stale_seconds=effective_stale,
        )

    await engine.dispose()

    items = summary["items"]
    if not items:
        console.print("[dim]No active workers.[/dim]")
        return

    console.print(
        "[bold]Workers:[/bold] "
        f"{summary['active_total']} active | "
        f"{summary['stale_total']} stale | "
        f"tail {summary['tail_active']} | "
        f"backfill {summary['backfill_active']} | "
        f"snapshot {summary['stats_active']} | "
        f"maintenance {summary['maintenance_active']}"
    )

    table = Table(title=f"Active Workers (stale_seconds={effective_stale})")
    table.add_column("Worker ID", style="cyan")
    table.add_column("Kind", style="magenta")
    table.add_column("Status", style="yellow")
    table.add_column("Log", style="white", max_width=32)
    table.add_column("Work", style="white", max_width=32)
    table.add_column("Last Seen")
    table.add_column("Error", style="red", max_width=48)

    for item in items:
        heartbeat_age = _format_age(int(item["last_heartbeat_age_seconds"]))
        table.add_row(
            str(item["worker_id"]),
            str(item["worker_kind"]),
            _format_status(item),
            _format_log(item),
            _format_work(item),
            heartbeat_age,
            _format_error(item),
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

        await reap_stale_worker_rows(session, stale_seconds=effective_stale)
        await session.commit()

    await engine.dispose()
    console.print(
        f"[green]Reaped {len(stale_rows)} stale worker row(s) "
        f"(threshold={effective_stale}s).[/green]"
    )
