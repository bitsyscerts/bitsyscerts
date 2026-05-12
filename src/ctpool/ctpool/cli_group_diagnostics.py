"""``ctpool diagnostics`` sub-command group.

Exposes operator diagnostic and health-check commands under a single
grouped entry point.  Advanced audit/repair commands remain accessible
via the top-level ``check-audit-gaps`` and ``fix-audit-findings``
commands.

Sub-commands:
    diagnostics doctor        — Run health checks (wraps ``doctor``).
    diagnostics entry-errors  — List recent entry failures (wraps
                                 ``entry-errors``).
    diagnostics legacy-ranges — Inspect legacy backfill range rows.
    diagnostics audit-gaps    — Advanced: detect audit gaps (dry-run safe).
"""

from __future__ import annotations

import asyncio
import uuid
from typing import Annotated

import typer
from rich.console import Console

_console = Console()


def register(app: typer.Typer) -> None:
    """Add the ``diagnostics`` sub-app to *app*."""
    diag_app = typer.Typer(
        help="Operator health checks and diagnostic tools.",
        no_args_is_help=True,
    )
    app.add_typer(diag_app, name="diagnostics")

    @diag_app.command("doctor")
    def doctor(
        strict: Annotated[
            bool,
            typer.Option(
                "--strict",
                help="Exit non-zero on warnings as well as errors.",
            ),
        ] = False,
        json: Annotated[
            bool,
            typer.Option("--json", help="Emit machine-readable JSON output."),
        ] = False,
        expect_workers: Annotated[
            bool,
            typer.Option(
                "--expect-workers",
                help="Treat stale ingestion metrics as a WARNING.",
            ),
        ] = False,
    ) -> None:
        """Run health checks and report the status of this instance."""
        from ctpool._cli_doctor_impl import run_doctor_command

        exit_code = asyncio.run(
            run_doctor_command(
                strict=strict,
                json_output=json,
                expect_workers=expect_workers,
                console=_console,
            )
        )
        raise typer.Exit(code=exit_code)

    @diag_app.command("entry-errors")
    def entry_errors(
        log_id: Annotated[
            uuid.UUID | None,
            typer.Option("--log-id", help="Filter by CT log UUID."),
        ] = None,
        outcome: Annotated[
            str | None,
            typer.Option(
                "--outcome",
                help=(
                    "Filter by outcome (parse_error / "
                    "unsupported_entry_type / write_error / "
                    "skipped_by_policy)."
                ),
            ),
        ] = None,
        limit: Annotated[
            int,
            typer.Option("--limit", help="Maximum rows to display (1..1000)."),
        ] = 100,
    ) -> None:
        """List recent terminal entry-failure rows from ct_entry_outcomes."""
        from ctpool._cli_entry_errors_impl import run_entry_errors

        asyncio.run(
            run_entry_errors(
                log_id=log_id,
                outcome_filter=outcome,
                limit=limit,
                console=_console,
            )
        )

    @diag_app.command("legacy-ranges")
    def legacy_ranges(
        dry_run: Annotated[
            bool,
            typer.Option(
                "--dry-run",
                help="Report row count without deleting.",
            ),
        ] = True,
    ) -> None:
        """[advanced/debug] Inspect legacy ct_log_backfill_ranges row counts.

        To clear rows, use ``ctpool legacy-ranges clear [--dry-run]``.
        """
        from ctpool.cli_legacy_commands import _query_status_counts  # noqa: PLC2701

        counts = asyncio.run(_query_status_counts())
        if not counts:
            _console.print("[dim]No legacy range rows present.[/dim]")
            return
        _console.print("[bold]Legacy ct_log_backfill_ranges status counts:[/bold]")
        for status_val, n in sorted(counts.items()):
            _console.print(f"  {status_val}: {n}")
        _console.print("[dim]Use 'ctpool legacy-ranges clear' to remove rows.[/dim]")

    @diag_app.command("audit-gaps")
    def audit_gaps(
        dry_run: Annotated[
            bool,
            typer.Option(
                "--dry-run",
                help="Report findings without persisting them.",
            ),
        ] = False,
    ) -> None:
        """[advanced/debug] Detect CT ingestion audit gaps."""
        from ctpool._cli_check_audit_impl import run_check_audit_gaps

        asyncio.run(run_check_audit_gaps(dry_run=dry_run, console=_console))
