"""Async implementation for the check-audit-gaps CLI command.

Extracted from cli.py to keep that module under the 500-line limit.
"""

from __future__ import annotations

from rich.console import Console

from ctpool.audit_checker import AuditCheckResult, run_all_checks
from ctpool.config import get_settings
from ctpool.db import create_engine, create_session_factory


async def run_check_audit_gaps(
    dry_run: bool,
    console: Console,
) -> AuditCheckResult:
    """Detect CT audit gaps and persist new findings.

    Args:
        dry_run: When True, report what would be written but do not commit.
        console: Rich console for output.

    Returns:
        AuditCheckResult with per-type counts of new findings.
    """
    settings = get_settings()
    engine = create_engine(str(settings.database_url))
    session_factory = create_session_factory(engine)

    claim_timeout = settings.ct_backfill_claim_timeout_seconds

    async with session_factory() as session:
        async with session.begin():
            result = await run_all_checks(session, claim_timeout)
            if dry_run:
                await session.rollback()
                console.print("[yellow]Dry run — no findings written.[/yellow]")
            else:
                console.print("[green]Findings persisted.[/green]")

    await engine.dispose()
    _print_results(result, dry_run, console)
    return result


def _print_results(
    result: AuditCheckResult,
    dry_run: bool,
    console: Console,
) -> None:
    """Print a human-readable summary of audit check results."""
    prefix = "[yellow][DRY RUN][/yellow] " if dry_run else ""
    if result.total_new_findings == 0:
        console.print(f"{prefix}[green]No new audit findings detected.[/green]")
        return
    console.print(
        f"{prefix}[bold]New audit findings[/bold]: {result.total_new_findings} total"
    )
    if result.stale_claims:
        console.print(f"  stale_backfill_claim:                 {result.stale_claims}")
    if result.failed_ranges:
        console.print(f"  failed_backfill_range:                {result.failed_ranges}")
    if result.missing_outcomes:
        console.print(
            f"  missing_entry_outcomes:               {result.missing_outcomes}"
        )
    if result.missing_observations:
        console.print(
            f"  missing_observations_without_outcome: {result.missing_observations}"
        )
