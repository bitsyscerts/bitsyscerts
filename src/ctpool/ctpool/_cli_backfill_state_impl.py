"""Async impl for ``ctpool backfill-state`` CLI command."""

from __future__ import annotations

import logging

from rich.console import Console
from rich.table import Table

from ctpool.backfill_state_queries import query_backfill_state_summary
from ctpool.config import get_settings
from ctpool.db import create_engine, create_session_factory

_logger = logging.getLogger(__name__)


def _format_progress(value: float | None) -> str:
    """Return a human-readable progress percentage or ``-``."""
    if value is None:
        return "-"
    return f"{value:.1f}%"


def _format_index(value: int | None) -> str:
    """Format a possibly-null log index for display."""
    return f"{value:,}" if value is not None else "-"


def _build_state_table(items: list[dict[str, object]]) -> Table:
    """Build the Rich table for one backfill_state snapshot."""
    table = Table(title="Per-log Backfill State")
    table.add_column("Log", style="cyan", no_wrap=False)
    table.add_column("Status")
    table.add_column("Claimed By")
    table.add_column("Checkpoint", justify="right")
    table.add_column("Window", justify="right")
    table.add_column("Progress", justify="right")
    table.add_column("Stale")

    for item in items:
        status = str(item["status"])
        is_stale = bool(item.get("is_stale", False))
        status_render = f"[red]{status}[/red]" if is_stale else status
        start = item.get("backfill_start_index")
        end = item.get("backfill_end_index")
        start_int = start if isinstance(start, int) else None
        end_int = end if isinstance(end, int) else None
        window = (
            f"{_format_index(start_int)} → {_format_index(end_int)}"
            if start_int is not None or end_int is not None
            else "-"
        )
        checkpoint = item.get("checkpoint_index")
        checkpoint_int = checkpoint if isinstance(checkpoint, int) else None
        progress = item.get("progress_percent")
        progress_float = progress if isinstance(progress, float) else None
        table.add_row(
            str(item.get("log_name") or item["log_source_id"]),
            status_render,
            str(item.get("claimed_by") or "-"),
            _format_index(checkpoint_int),
            window,
            _format_progress(progress_float),
            "yes" if is_stale else "no",
        )
    return table


async def run_list_backfill_state() -> None:
    """Print one row per log from ``ct_log_backfill_state``."""
    settings = get_settings()
    console = Console()
    engine = create_engine(settings)
    session_factory = create_session_factory(engine)

    async with session_factory() as session:
        summary = await query_backfill_state_summary(
            session,
            stale_seconds=settings.ct_worker_stale_seconds,
        )

    items = list(summary.get("items", []))
    if not items:
        console.print(
            "[yellow]No backfill state rows found. Run 'ctpool sync-logs' "
            "and start a backfill worker to initialize windows.[/yellow]"
        )
        await engine.dispose()
        return

    console.print(_build_state_table(items))
    counters = {k: v for k, v in summary.items() if k != "items"}
    summary_line = " ".join(f"{k}={v}" for k, v in counters.items())
    console.print(f"\n[dim]{summary_line}[/dim]")
    await engine.dispose()
