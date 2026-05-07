"""Async implementation for the fix-audit-findings CLI command.

Extracted from cli.py to keep that module under the 500-line limit.
"""

from __future__ import annotations

import logging
import uuid

from rich.console import Console

from ctpool.audit_constants import (
    ALL_FINDING_TYPES,
    ALL_SEVERITIES,
    DEFAULT_REPAIR_SEVERITIES,
    SEVERITY_WARNING,
)
from ctpool.audit_repair import (
    RepairOptions,
    apply_repair,
    fetch_repairable_findings,
    mark_finding_ignored,
)
from ctpool.config import get_settings
from ctpool.db import create_engine, create_session_factory

_logger = logging.getLogger(__name__)


async def run_fix_audit_findings(
    dry_run: bool,
    finding_id: uuid.UUID | None,
    finding_type: str | None,
    severity_filter: str | None,
    limit: int,
    include_warnings: bool,
    console: Console,
) -> int:
    """Load repairable findings, apply repairs, and report results.

    Args:
        dry_run:          When True, annotate but do not commit.
        finding_id:       Narrow to a single finding UUID.
        finding_type:     Filter by finding type string.
        severity_filter:  Comma-separated severity values (override default).
        limit:            Maximum findings to process.
        include_warnings: When True, add severity=warning to default set.
        console:          Rich console for output.

    Returns:
        Count of findings processed (attempted repairs).
    """
    if finding_type is not None and finding_type not in ALL_FINDING_TYPES:
        console.print(
            f"[red]Unknown finding type: {finding_type!r}[/red]\n"
            f"Valid types: {sorted(ALL_FINDING_TYPES)}"
        )
        return 0

    severities = _resolve_severities(severity_filter, include_warnings)

    options = RepairOptions(
        finding_id=finding_id,
        finding_type=finding_type,
        severities=severities,
        limit=limit,
        dry_run=dry_run,
    )

    settings = get_settings()
    engine = create_engine(settings)
    session_factory = create_session_factory(engine)

    processed = 0
    errors = 0
    try:
        async with session_factory() as session:
            findings = await fetch_repairable_findings(session, options)
            if not findings:
                console.print("[green]No repairable findings found.[/green]")
                return 0
            for finding in findings:
                sp = await session.begin_nested()
                try:
                    updated = await apply_repair(finding, session)
                    if dry_run:
                        await sp.rollback()
                    else:
                        await sp.commit()
                except Exception as exc:
                    await sp.rollback()
                    _logger.warning(
                        "Repair failed for finding %s (%s): %s",
                        finding.id,
                        finding.finding_type,
                        exc,
                    )
                    errors += 1
                    continue
                _print_repair_line(updated, dry_run, console)
                processed += 1
            if not dry_run and processed > 0:
                await session.commit()
    finally:
        await engine.dispose()

    _print_summary(processed, errors, dry_run, console)
    return processed


async def run_mark_ignored(
    finding_id: uuid.UUID,
    reason: str,
    console: Console,
) -> bool:
    """Mark a single finding as ignored.

    Returns:
        True when the finding was found and updated; False when not found.
    """
    settings = get_settings()
    engine = create_engine(settings)
    session_factory = create_session_factory(engine)

    try:
        async with session_factory() as session:
            async with session.begin():
                finding = await mark_finding_ignored(session, finding_id, reason)
                found = finding is not None
    finally:
        await engine.dispose()
    if found:
        console.print(f"[green]Finding {finding_id} marked as ignored.[/green]")
    else:
        console.print(f"[red]Finding {finding_id} not found.[/red]")
    return found


def _resolve_severities(
    severity_filter: str | None,
    include_warnings: bool,
) -> frozenset[str]:
    """Build the effective severity frozenset from CLI options."""
    if severity_filter is not None:
        parts = {s.strip() for s in severity_filter.split(",")}
        unknown = parts - ALL_SEVERITIES
        if unknown:
            raise ValueError(
                f"Unknown severities: {unknown}. Valid: {sorted(ALL_SEVERITIES)}"
            )
        return frozenset(parts)
    base = set(DEFAULT_REPAIR_SEVERITIES)
    if include_warnings:
        base.add(SEVERITY_WARNING)
    return frozenset(base)


def _print_repair_line(
    finding: object,
    dry_run: bool,
    console: Console,
) -> None:
    """Print one repair result line."""
    prefix = "[yellow][DRY RUN][/yellow] " if dry_run else ""
    console.print(
        f"{prefix}"
        f"id={getattr(finding, 'id', '?')} "
        f"type={getattr(finding, 'finding_type', '?')} "
        f"→ status={getattr(finding, 'status', '?')} "
        f"action={getattr(finding, 'repair_action', '?')}"
    )


def _print_summary(
    count: int,
    errors: int,
    dry_run: bool,
    console: Console,
) -> None:
    """Print the final processed-count summary."""
    mode = "Dry-run processed" if dry_run else "Repaired"
    console.print(f"[bold]{mode}[/bold]: {count} finding(s).")
    if errors:
        console.print(f"[red]Failed[/red]: {errors} finding(s) could not be repaired.")
