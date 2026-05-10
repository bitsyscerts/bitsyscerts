"""Diagnostics CLI commands for normal operator workflows.

These are not advanced/debug audit tools — they expose self-healing
ingestion state so operators can see what per-log workers are doing
without engaging the legacy audit/repair subsystem.

Commands:
    entry-errors — List recent terminal entry-failure rows (bounded).
"""

from __future__ import annotations

import asyncio
import uuid
from typing import Annotated

import typer
from rich.console import Console

_console = Console()


def register(app: typer.Typer) -> None:
    """Register diagnostics commands on *app*."""

    @app.command("entry-errors")
    def entry_errors(
        log_id: Annotated[
            uuid.UUID | None,
            typer.Option("--log-id", help="Filter by CT log UUID."),
        ] = None,
        outcome: Annotated[
            str | None,
            typer.Option(
                "--outcome",
                help="Filter by outcome (parse_error / unsupported_entry_type / "
                "write_error / skipped_by_policy).",
            ),
        ] = None,
        limit: Annotated[
            int,
            typer.Option("--limit", help="Maximum rows to display (1..1000)."),
        ] = 100,
    ) -> None:
        """List recent terminal entry-failure rows from ct_entry_outcomes.

        Shows a bounded, time-ordered view of per-entry failures recorded
        by per-log workers. Use this to diagnose ingestion problems
        before reaching for the advanced audit/repair commands.
        """
        from ctpool._cli_entry_errors_impl import run_entry_errors

        asyncio.run(
            run_entry_errors(
                log_id=log_id,
                outcome_filter=outcome,
                limit=limit,
                console=_console,
            )
        )
