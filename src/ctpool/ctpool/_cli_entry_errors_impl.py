"""Async implementation for the ``ctpool entry-errors`` CLI command.

Lists recent terminal entry-failure rows from ``ct_entry_outcomes`` in a
bounded, operator-friendly form. This is a normal diagnostics command —
not a legacy audit/repair tool — so per-log workers' self-healing
state can be inspected without engaging the audit subsystem.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from rich.console import Console
from rich.table import Table
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from ctpool.config import get_settings
from ctpool.db import create_engine, create_session_factory
from ctpool.models.entry_outcome import CtEntryOutcome
from ctpool.models.log_source import CtLogSource
from ctpool.outcome_constants import OUTCOME_STORED


async def run_entry_errors(
    *,
    log_id: uuid.UUID | None,
    outcome_filter: str | None,
    limit: int,
    console: Console,
) -> int:
    """Render the most recent terminal entry-failure rows.

    Returns the number of rows shown. Intentionally bounded — never
    streams the entire ``ct_entry_outcomes`` table.
    """
    settings = get_settings()
    engine = create_engine(settings)
    session_factory = create_session_factory(engine)
    try:
        async with session_factory() as session:
            rows = await _fetch_entry_error_rows(
                session,
                log_id=log_id,
                outcome_filter=outcome_filter,
                limit=limit,
            )
    finally:
        await engine.dispose()

    _render_table(rows, console)
    return len(rows)


async def _fetch_entry_error_rows(
    session: AsyncSession,
    *,
    log_id: uuid.UUID | None,
    outcome_filter: str | None,
    limit: int,
) -> list[dict[str, Any]]:
    """Bounded query — never returns more than *limit* rows."""
    bounded = max(1, min(limit, 1000))
    stmt = (
        select(
            CtEntryOutcome.log_source_id,
            CtEntryOutcome.log_index,
            CtEntryOutcome.outcome,
            CtEntryOutcome.error_message,
            CtEntryOutcome.last_seen_at,
            CtLogSource.description,
        )
        .join(CtLogSource, CtLogSource.id == CtEntryOutcome.log_source_id)
        .where(CtEntryOutcome.outcome != OUTCOME_STORED)
        .order_by(desc(CtEntryOutcome.last_seen_at))
        .limit(bounded)
    )
    if log_id is not None:
        stmt = stmt.where(CtEntryOutcome.log_source_id == log_id)
    if outcome_filter is not None:
        stmt = stmt.where(CtEntryOutcome.outcome == outcome_filter)
    rows = (await session.execute(stmt)).all()
    return [
        {
            "log_source_id": row.log_source_id,
            "log_name": row.description,
            "log_index": row.log_index,
            "outcome": row.outcome,
            "error_message": row.error_message,
            "last_seen_at": row.last_seen_at,
        }
        for row in rows
    ]


def _render_table(rows: list[dict[str, Any]], console: Console) -> None:
    """Render a Rich table summarizing the rows."""
    if not rows:
        console.print("[green]No terminal entry errors found.[/green]")
        return
    table = Table(title=f"Recent terminal entry errors ({len(rows)})")
    table.add_column("when", style="cyan")
    table.add_column("log")
    table.add_column("index", justify="right")
    table.add_column("outcome", style="yellow")
    table.add_column("message")
    now = datetime.now(UTC)
    for row in rows:
        observed: datetime | None = row["last_seen_at"]
        when = ""
        if observed is not None:
            age_seconds = int((now - observed.replace(tzinfo=UTC)).total_seconds())
            when = f"{age_seconds}s ago"
        message = (row["error_message"] or "")[:80]
        table.add_row(
            when,
            row["log_name"] or str(row["log_source_id"]),
            str(row["log_index"]),
            row["outcome"],
            message,
        )
    console.print(table)
