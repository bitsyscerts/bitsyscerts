"""Async implementation helpers for the reap-stale-backfill-claims and
prune-metrics CLI commands.

Extracted from cli.py to keep that module under the 500-line limit.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from rich.console import Console
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ctpool.config import get_settings
from ctpool.db import create_engine, create_session_factory
from ctpool.models.log_backfill_range import CtLogBackfillRange


async def _dry_run_reap(
    session: AsyncSession,
    cutoff: datetime,
    effective_timeout: int,
    console: Console,
) -> None:
    """Report stale claims without resetting them."""
    result = await session.execute(
        select(
            CtLogBackfillRange.id,
            CtLogBackfillRange.log_source_id,
            CtLogBackfillRange.start_index,
            CtLogBackfillRange.end_index,
            CtLogBackfillRange.next_index,
        )
        .where(CtLogBackfillRange.status == "in_progress")
        .where(
            func.coalesce(
                CtLogBackfillRange.heartbeat_at,
                CtLogBackfillRange.claimed_at,
            )
            < cutoff
        )
    )
    rows = result.all()
    if not rows:
        console.print(
            f"[green]No stale claims found (timeout={effective_timeout}s).[/green]"
        )
        return
    console.print(
        f"[yellow]Would reset {len(rows)} stale claim(s) "
        f"(timeout={effective_timeout}s):[/yellow]"
    )
    for r in rows:
        console.print(
            f"  range={r.id} log={r.log_source_id} "
            f"[{r.start_index:,}–{r.end_index:,}] next={r.next_index:,}"
        )


async def run_reap_stale(
    *,
    dry_run: bool,
    timeout_seconds: int | None,
    console: Console,
) -> None:
    """Async implementation of reap-stale-backfill-claims."""
    from ctpool.dispatcher import reap_stale_backfill_claims as _reap

    settings = get_settings()
    effective_timeout = (
        timeout_seconds
        if timeout_seconds is not None
        else settings.ct_backfill_claim_timeout_seconds
    )
    engine = create_engine(settings)
    factory = create_session_factory(engine)

    if dry_run:
        cutoff = datetime.now(UTC) - timedelta(seconds=effective_timeout)
        async with factory() as session:
            await _dry_run_reap(session, cutoff, effective_timeout, console)
    else:
        async with factory() as session:
            async with session.begin():
                reaped = await _reap(session, effective_timeout)
        if not reaped:
            console.print(
                f"[green]No stale claims found (timeout={effective_timeout}s).[/green]"
            )
        else:
            console.print(
                f"[green]Reset {len(reaped)} stale claim(s) "
                f"(timeout={effective_timeout}s).[/green]"
            )
            for r in reaped:
                console.print(
                    f"  range={r.id} log={r.log_source_id} "
                    f"[{r.start_index:,}–{r.end_index:,}] next={r.next_index:,}"
                )

    await engine.dispose()


async def run_prune_metrics(
    *,
    dry_run: bool,
    retention_days: int | None,
    console: Console,
) -> None:
    """Async implementation of prune-metrics."""
    from ctpool.metrics import prune_ingestion_metrics

    settings = get_settings()
    effective_days = (
        retention_days
        if retention_days is not None
        else settings.ct_metrics_retention_days
    )
    engine = create_engine(settings)
    factory = create_session_factory(engine)
    async with factory() as session:
        if not dry_run:
            async with session.begin():
                deleted = await prune_ingestion_metrics(
                    session, effective_days, dry_run=False
                )
        else:
            deleted = await prune_ingestion_metrics(
                session, effective_days, dry_run=True
            )
    await engine.dispose()
    action = "Would delete" if dry_run else "Deleted"
    console.print(
        f"[green]{action} {deleted:,} ingestion_metrics row(s) "
        f"(retention={effective_days}d).[/green]"
    )
