"""Query the database and render per-log ingestion statistics.

Exports:
    render_stats       — Render a one-shot stats table to a Rich console.
    render_stats_watch — Continuously refresh stats at a given interval.
"""

from __future__ import annotations

import asyncio

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from ctpool.models.certificate import Certificate
from ctpool.models.hostname import Hostname
from ctpool.models.log_source import CtLogSource

_SIZE_TABLES: list[str] = [
    "certificates",
    "hostnames",
    "ct_log_sources",
    "ct_log_tail_cursors",
    "ct_log_backfill_ranges",
    "ingestion_errors",
]


async def _query_db_size(
    session: AsyncSession,
) -> tuple[str, list[tuple[str, int]]]:
    """Return (total_db_size_pretty, [(table_name, row_count), ...])."""
    size_result = await session.execute(
        text("SELECT pg_size_pretty(pg_database_size(current_database()))")
    )
    total_size: str = size_result.scalar_one() or "?"

    rows: list[tuple[str, int]] = []
    for table in _SIZE_TABLES:
        count_result = await session.execute(
            text(f"SELECT COUNT(*) FROM {table}")  # noqa: S608
        )
        rows.append((table, int(count_result.scalar_one())))
    return total_size, rows


def _build_size_panel(
    total_size: str,
    table_rows: list[tuple[str, int]],
) -> Panel:
    """Build a Rich Panel showing per-table row counts and total DB disk size."""
    lines = [f"[bold]Total DB size:[/bold] [cyan]{total_size}[/cyan]\n"]
    for table, count in table_rows:
        lines.append(f"  {table:<32} {count:>12,}")
    return Panel(
        "\n".join(lines),
        title="Database Storage",
        border_style="dim",
        expand=False,
    )


async def _query_totals(session: AsyncSession) -> tuple[int, int]:
    """Return ``(cert_count, hostname_count)`` from the database."""
    cert_result = await session.execute(select(func.count()).select_from(Certificate))
    host_result = await session.execute(select(func.count()).select_from(Hostname))
    return int(cert_result.scalar_one()), int(host_result.scalar_one())


async def _query_log_rows(session: AsyncSession) -> list[CtLogSource]:
    """Load all CtLogSource rows with runtime_state and tail_cursor."""
    stmt = select(CtLogSource).options(
        selectinload(CtLogSource.runtime_state),
        selectinload(CtLogSource.tail_cursor),
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


_HEALTH_COLORS: dict[str, str] = {
    "ok": "green",
    "error": "red",
    "degraded": "yellow",
}


def _make_log_row(log: CtLogSource) -> tuple[str, str, str, str, str, str]:
    """Return display strings for a single CtLogSource table row."""
    health = log.runtime_state.health_status if log.runtime_state else "—"
    tree_size = log.runtime_state.tree_size if log.runtime_state else None
    cursor = log.tail_cursor.next_index if log.tail_cursor else None
    tree_str = f"{tree_size:,}" if tree_size is not None else "—"
    cursor_str = f"{cursor:,}" if cursor is not None else "—"
    if tree_size is not None and cursor is not None:
        lag = max(0, tree_size - cursor)
        lag_str = f"{lag:,}"
        sync_pct_str = f"{cursor / tree_size * 100:.1f}%" if tree_size > 0 else "—"
    else:
        lag_str = "—"
        sync_pct_str = "—"
    color = _HEALTH_COLORS.get(health, "white")
    return (
        log.description[:40],
        f"[{color}]{health}[/{color}]",
        tree_str,
        cursor_str,
        lag_str,
        sync_pct_str,
    )


def _build_stats_table(
    logs: list[CtLogSource],
    cert_count: int,
    hostname_count: int,
) -> Table:
    """Build a Rich Table from collected stats data."""
    title = (
        f"CT Pool Statistics | Certs: {cert_count:,} | Hostnames: {hostname_count:,}"
    )
    table = Table(title=title, show_header=True, header_style="bold magenta")
    table.add_column("Log", style="cyan", min_width=20)
    table.add_column("Health", justify="center", min_width=8)
    table.add_column("Tree Size", justify="right", min_width=12)
    table.add_column("Tail Next", justify="right", min_width=12)
    table.add_column("Tail Lag", justify="right", min_width=12)
    table.add_column("Sync %", justify="right", min_width=8)
    for log in logs:
        table.add_row(*_make_log_row(log))
    return table


async def render_stats(session: AsyncSession, console: Console) -> None:
    """Render a one-shot statistics table to *console*.

    Args:
        session: Active async database session.
        console: Rich Console to print to.
    """
    cert_count, hostname_count = await _query_totals(session)
    logs = await _query_log_rows(session)
    total_size, table_rows = await _query_db_size(session)
    table = _build_stats_table(logs, cert_count, hostname_count)
    console.print(table)
    console.print(_build_size_panel(total_size, table_rows))


async def render_stats_watch(
    session_factory: async_sessionmaker[AsyncSession],
    console: Console,
    interval_seconds: int = 5,
) -> None:
    """Continuously refresh statistics every *interval_seconds* seconds.

    Runs until cancelled (``asyncio.CancelledError`` or ``KeyboardInterrupt``).

    Args:
        session_factory:  Factory for creating new database sessions.
        console:          Rich Console to print to.
        interval_seconds: Refresh interval in seconds.
    """
    while True:
        console.clear()
        async with session_factory() as session:
            await render_stats(session, console)
        await asyncio.sleep(interval_seconds)
