"""Query the database and render per-log ingestion statistics.

# NOTE (201–500 line warning zone): all functions here are tightly coupled
# display/query helpers for one screen. Splitting into two modules would
# require cross-module sharing of thin helper types with no cohesion benefit.

Exports:
    render_stats       — Render a one-shot stats table to a Rich console.
    render_stats_watch — Continuously refresh stats at a given interval.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime, timedelta

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from ctpool.db_contention_observability import read_db_contention_operator_snapshot
from ctpool.models.certificate import Certificate
from ctpool.models.hostname import Hostname
from ctpool.models.ingestion_metric import IngestionMetric
from ctpool.models.log_source import CtLogSource
from ctpool.stats_contention import render_db_contention_panel

_THROUGHPUT_WINDOW_MINUTES: int = 10

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


def _format_eta(lag_entries: int, rate_per_sec: float | None) -> str:
    """Convert lag + rate to a human-readable ETA string.

    Returns ``"—"`` when rate is None, zero, or lag is zero.
    Format: ``ddd.hh:mm:ss`` when days >= 1, else ``hh:mm:ss``.
    """
    if not rate_per_sec or lag_entries <= 0:
        return "—"
    total_seconds = int(lag_entries / rate_per_sec)
    days, remainder = divmod(total_seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, seconds = divmod(remainder, 60)
    if days > 0:
        return f"{days}.{hours:02d}:{minutes:02d}:{seconds:02d}"
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


async def _query_recent_throughputs(
    session: AsyncSession,
) -> dict[uuid.UUID, float]:
    """Return avg throughput per log for the last _THROUGHPUT_WINDOW_MINUTES minutes.

    Only logs with at least one recent snapshot row are included.
    Absent key means no recent data — caller should show ``"—"``.
    """
    cutoff = datetime.now(UTC) - timedelta(minutes=_THROUGHPUT_WINDOW_MINUTES)
    stmt = (
        select(
            IngestionMetric.log_source_id,
            func.avg(IngestionMetric.throughput_entries_per_sec).label("avg_rate"),
        )
        .where(IngestionMetric.snapshot_at > cutoff)
        .group_by(IngestionMetric.log_source_id)
    )
    result = await session.execute(stmt)
    return {
        row.log_source_id: float(row.avg_rate)
        for row in result
        if row.avg_rate is not None
    }


def _make_log_row(
    log: CtLogSource,
    rate_per_sec: float | None,
) -> tuple[str, str, str, str, str, str, str]:
    # NOTE (21–50 line warning zone): the branches for missing vs. present
    # runtime state are an inseparable conditional unit; extracting further
    # sub-functions would require passing 4+ return values across boundaries.
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
        eta_str = _format_eta(lag, rate_per_sec)
    else:
        lag_str = "—"
        sync_pct_str = "—"
        eta_str = "—"
    color = _HEALTH_COLORS.get(health, "white")
    return (
        log.description[:40],
        f"[{color}]{health}[/{color}]",
        tree_str,
        cursor_str,
        lag_str,
        sync_pct_str,
        eta_str,
    )


def _build_stats_table(
    logs: list[CtLogSource],
    cert_count: int,
    hostname_count: int,
    throughputs: dict[uuid.UUID, float],
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
    table.add_column("Est.", justify="right", min_width=12)
    for log in logs:
        table.add_row(*_make_log_row(log, throughputs.get(log.id)))
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
    throughputs = await _query_recent_throughputs(session)
    contention_snapshot = await read_db_contention_operator_snapshot(session)
    table = _build_stats_table(logs, cert_count, hostname_count, throughputs)
    console.print(table)
    console.print(render_db_contention_panel(contention_snapshot))
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
