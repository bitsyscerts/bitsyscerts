"""Implementation for the prune-entry-outcomes CLI command.

Exports:
    run_prune_entry_outcomes — Execute or dry-run the entry-outcome prune operation.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from rich.console import Console

from ctpool.config import get_settings
from ctpool.db import create_engine, create_session_factory
from ctpool.models.entry_outcome import CtEntryOutcome

_logger = logging.getLogger(__name__)

_DEFAULT_BATCH_SIZE: int = 5_000
_DEFAULT_LIMIT: int = 0


async def run_prune_entry_outcomes(
    *,
    dry_run: bool = True,
    retention_days: int | None = None,
    batch_size: int = _DEFAULT_BATCH_SIZE,
    limit: int = _DEFAULT_LIMIT,
    console: Console,
) -> int:
    """Delete ct_entry_outcomes rows older than the retention window.

    Args:
        dry_run:        If True (default), only count candidates without deleting.
        retention_days: Override config ``ct_entry_outcome_retention_days``.
        batch_size:     Rows to delete per transaction.
        limit:          Max rows to delete total (0 = unlimited).
        console:        Rich console for output.

    Returns:
        Number of rows deleted (0 in dry-run mode).
    """
    from sqlalchemy import delete, func, select

    settings = get_settings()
    days = (
        retention_days
        if retention_days is not None
        else settings.ct_entry_outcome_retention_days
    )
    cutoff = datetime.now(UTC) - timedelta(days=days)
    mode_label = "dry-run" if dry_run else "execute"

    console.print(
        f"[bold]prune-entry-outcomes[/bold] | mode={mode_label} | "
        f"retention={days}d | cutoff={cutoff.date().isoformat()}"
    )

    engine = create_engine(settings)
    factory = create_session_factory(engine)

    async with factory() as session:
        count_stmt = (
            select(func.count())
            .where(CtEntryOutcome.first_seen_at < cutoff)
            .select_from(CtEntryOutcome)
        )
        candidate_count = int((await session.execute(count_stmt)).scalar_one())

    console.print(f"  candidates: [cyan]{candidate_count:,}[/cyan]")

    if dry_run:
        console.print("  [yellow]Dry-run: no rows deleted.[/yellow]")
        await engine.dispose()
        return 0

    total_deleted = 0
    while True:
        if limit and total_deleted >= limit:
            break
        effective_batch = (
            min(batch_size, limit - total_deleted) if limit else batch_size
        )
        async with factory() as session:
            async with session.begin():
                subq = (
                    select(CtEntryOutcome.id)
                    .where(CtEntryOutcome.first_seen_at < cutoff)
                    .limit(effective_batch)
                    .scalar_subquery()
                )
                stmt = delete(CtEntryOutcome).where(CtEntryOutcome.id.in_(subq))
                result = await session.execute(stmt)
                deleted = result.rowcount
        if deleted == 0:
            break
        total_deleted += deleted
        _logger.debug(
            "Deleted %d entry-outcome rows (total=%d)", deleted, total_deleted
        )

    await engine.dispose()
    console.print(f"  Deleted [green]{total_deleted:,}[/green] entry-outcome rows.")
    return total_deleted
