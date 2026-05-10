"""Audit and health CLI commands.

Commands:
    check-audit-gaps   — Advanced diagnostic: legacy range/audit consistency.
    fix-audit-findings — Advanced repair for audit findings.
    doctor             — Run health checks and report status.

These audit and repair commands are advanced/debug tools. They are not
required for normal per-log dispatch operation; per-log workers handle
retryable failures inline.
"""

from __future__ import annotations

import asyncio
import uuid
from typing import Annotated

import typer
from rich.console import Console

_console = Console()


def register(app: typer.Typer) -> None:
    """Register all audit and health commands on *app*."""

    @app.command("check-audit-gaps")
    def check_audit_gaps(
        dry_run: Annotated[
            bool,
            typer.Option(
                "--dry-run",
                help="Report findings without persisting them.",
            ),
        ] = False,
    ) -> None:
        """[advanced/debug] Detect CT ingestion audit gaps and persist findings.

        Advanced diagnostic command for legacy range/audit consistency
        checks. Not required for normal per-log dispatch operation.
        """
        from ctpool._cli_check_audit_impl import run_check_audit_gaps

        asyncio.run(run_check_audit_gaps(dry_run=dry_run, console=_console))

    @app.command("fix-audit-findings")
    def fix_audit_findings(
        dry_run: Annotated[
            bool,
            typer.Option(
                "--dry-run",
                help="Annotate findings without committing repairs.",
            ),
        ] = False,
        finding_id: Annotated[
            uuid.UUID | None,
            typer.Option("--finding-id", help="Target a specific finding UUID."),
        ] = None,
        finding_type: Annotated[
            str | None,
            typer.Option("--type", help="Filter by finding type."),
        ] = None,
        severity: Annotated[
            str | None,
            typer.Option(
                "--severity",
                help="Comma-separated severities (overrides default).",
            ),
        ] = None,
        limit: Annotated[
            int,
            typer.Option("--limit", help="Maximum findings to process."),
        ] = 100,
        include_warnings: Annotated[
            bool,
            typer.Option(
                "--include-warnings",
                help="Include severity=warning findings.",
            ),
        ] = False,
        mark_ignored: Annotated[
            uuid.UUID | None,
            typer.Option("--mark-ignored", help="Mark a specific finding as ignored."),
        ] = None,
        mark_ignored_reason: Annotated[
            str,
            typer.Option(
                "--mark-ignored-reason",
                help="Reason for ignoring the finding.",
            ),
        ] = "",
    ) -> None:
        """[advanced/debug] Apply conservative repairs to open CT audit findings.

        Advanced repair command for audit findings. Normal retryable
        ingestion failures should be handled inline by per-log workers.
        """
        from ctpool._cli_repair_audit_impl import (
            run_fix_audit_findings,
            run_mark_ignored,
        )

        if mark_ignored is not None:
            asyncio.run(run_mark_ignored(mark_ignored, mark_ignored_reason, _console))
            return
        asyncio.run(
            run_fix_audit_findings(
                dry_run=dry_run,
                finding_id=finding_id,
                finding_type=finding_type,
                severity_filter=severity,
                limit=limit,
                include_warnings=include_warnings,
                console=_console,
            )
        )

    @app.command("doctor")
    def doctor(
        strict: Annotated[
            bool,
            typer.Option("--strict", help="Exit non-zero even for WARNING."),
        ] = False,
        json_output: Annotated[
            bool,
            typer.Option("--json", help="Emit JSON instead of the Rich table."),
        ] = False,
        expect_workers: Annotated[
            bool,
            typer.Option(
                "--expect-workers",
                help="Treat stale ingestion metrics as a WARNING.",
            ),
        ] = False,
    ) -> None:
        """Run health checks and report the status of this BitsysCerts instance."""
        from ctpool._cli_doctor_impl import run_doctor_command

        exit_code = asyncio.run(
            run_doctor_command(
                strict=strict,
                json_output=json_output,
                expect_workers=expect_workers,
                console=_console,
            )
        )
        raise typer.Exit(code=exit_code)
