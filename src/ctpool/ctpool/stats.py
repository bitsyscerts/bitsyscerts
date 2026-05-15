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
from sqlalchemy import func, select
from sqlalchemy import table as sa_table
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from ctpool.db_contention_observability import read_db_contention_operator_snapshot
from ctpool.models.certificate import Certificate
from ctpool.models.entry_outcome import CtEntryOutcome
from ctpool.models.hostname import Hostname
from ctpool.models.ingestion_metric import IngestionMetric
from ctpool.models.log_backfill_range import CtLogBackfillRange
from ctpool.models.log_source import CtLogSource
from ctpool.outcome_constants import ALL_OUTCOMES
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
        select(func.pg_size_pretty(func.pg_database_size(func.current_database())))
    )
    total_size: str = size_result.scalar_one() or "?"

    rows: list[tuple[str, int]] = []
    for table in _SIZE_TABLES:
        count_result = await session.execute(
            select(func.count()).select_from(sa_table(table))
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


async def _query_outcome_counts(session: AsyncSession) -> dict[str, int]:
    """Return per-outcome row counts from ``ct_entry_outcomes``."""
    stmt = select(CtEntryOutcome.outcome, func.count().label("cnt")).group_by(
        CtEntryOutcome.outcome
    )
    result = await session.execute(stmt)
    counts: dict[str, int] = dict.fromkeys(ALL_OUTCOMES, 0)
    for row in result:
        counts[row.outcome] = int(row.cnt)
    return counts


def _build_outcomes_panel(counts: dict[str, int]) -> Panel:
    """Build a Rich Panel showing per-outcome totals from ``ct_entry_outcomes``."""
    lines: list[str] = []
    for outcome in sorted(counts.keys()):
        lines.append(f"  {outcome:<30} {counts[outcome]:>12,}")
    body = "\n".join(lines) if lines else "  No outcomes recorded yet."
    return Panel(body, title="Entry Outcomes", border_style="dim", expand=False)


async def _query_backfill_range_counts(
    session: AsyncSession, claim_timeout_seconds: int
) -> dict[str, int]:
    """Return backfill range status counts, distinguishing stale in_progress claims."""
    cutoff = datetime.now(UTC) - timedelta(seconds=claim_timeout_seconds)
    stale_cond = (
        func.coalesce(CtLogBackfillRange.heartbeat_at, CtLogBackfillRange.claimed_at)
        < cutoff
    )
    stmt = select(
        func.count().filter(CtLogBackfillRange.status == "pending").label("pending"),
        func.count()
        .filter(CtLogBackfillRange.status == "in_progress", ~stale_cond)
        .label("in_progress"),
        func.count()
        .filter(CtLogBackfillRange.status == "in_progress", stale_cond)
        .label("stale"),
        func.count().filter(CtLogBackfillRange.status == "complete").label("complete"),
        func.count().filter(CtLogBackfillRange.status == "failed").label("failed"),
    ).select_from(CtLogBackfillRange)
    result = await session.execute(stmt)
    row = result.one()
    return {
        "pending": int(row.pending),
        "in_progress": int(row.in_progress),
        "stale": int(row.stale),
        "complete": int(row.complete),
        "failed": int(row.failed),
    }


def _build_backfill_ranges_panel(counts: dict[str, int]) -> Panel:
    """Build a Rich Panel showing backfill range status counts."""
    stale = counts.get("stale", 0)
    failed = counts.get("failed", 0)
    stale_style = "[red]" if stale > 0 else ""
    stale_end = "[/red]" if stale > 0 else ""
    failed_style = "[bold red]" if failed > 0 else ""
    failed_end = "[/bold red]" if failed > 0 else ""
    lines = [
        f"  {'pending':<20} {counts.get('pending', 0):>12,}",
        f"  {'in_progress (fresh)':<20} {counts.get('in_progress', 0):>12,}",
        f"  {stale_style}{'in_progress (stale)':<20} {stale:>12,}{stale_end}",
        f"  {'complete':<20} {counts.get('complete', 0):>12,}",
        f"  {failed_style}{'failed':<20} {failed:>12,}{failed_end}",
    ]
    if failed > 0:
        lines.append(
            f"\n  [bold red]WARNING: {failed:,} range(s) failed and will not be "
            "retried automatically.[/bold red]"
        )
    return Panel(
        "\n".join(lines),
        title="Backfill Range Status",
        border_style="dim",
        expand=False,
    )


async def render_stats(session: AsyncSession, console: Console) -> None:
    """Render a one-shot statistics table to *console*.

    Args:
        session: Active async database session.
        console: Rich Console to print to.
    """
    from ctpool.config import get_settings

    settings = get_settings()
    cert_count, hostname_count = await _query_totals(session)
    logs = await _query_log_rows(session)
    total_size, table_rows = await _query_db_size(session)
    throughputs = await _query_recent_throughputs(session)
    contention_snapshot = await read_db_contention_operator_snapshot(session)
    outcome_counts = await _query_outcome_counts(session)
    backfill_counts = await _query_backfill_range_counts(
        session, settings.ct_backfill_claim_timeout_seconds
    )
    table = _build_stats_table(logs, cert_count, hostname_count, throughputs)
    console.print(table)
    console.print(render_db_contention_panel(contention_snapshot))
    console.print(_build_size_panel(total_size, table_rows))
    console.print(_build_outcomes_panel(outcome_counts))
    console.print(_build_backfill_ranges_panel(backfill_counts))


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
