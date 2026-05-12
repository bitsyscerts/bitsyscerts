"""Helpers for the storage-profile prune orchestrator.

Splits the larger ``_cli_prune_storage_profile_impl`` module into focused
collaborators so that each function stays under the 20-line preferred
target while the orchestrator itself remains readable.

Exports:
    PruneCategory             — One row in the prune plan (settings + counts).
    PruneAggregate            — Aggregated deletion counters across categories.
    build_prune_plan          — Build the plan from active settings + overrides.
    summarize_plan_for_console — Render a plan to a Rich console (human form).
    summarize_plan_as_json    — Serialize the aggregate to a JSON-friendly dict.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class PruneCategory:
    """Plan row for a single retention category.

    ``retention_days == 0`` means "retain indefinitely" — the category is
    skipped entirely (no candidate count, no deletion).
    """

    name: str
    retention_days: int
    candidate_count: int = 0
    deleted_count: int = 0
    skipped_reason: str | None = None

    @property
    def is_disabled(self) -> bool:
        """Return True when retention is configured to keep all rows."""
        return self.retention_days <= 0


@dataclass
class PruneAggregate:
    """Aggregated outcome of a prune-for-storage-profile run."""

    storage_profile: str
    cert_storage_mode: str
    hostname_retention_mode: str
    started_at: datetime
    mode: str  # "dry_run" | "execute"

    deleted_certificates: int = 0
    deleted_certificate_hostnames: int = 0
    deleted_observations: int = 0
    deleted_entry_outcomes: int = 0
    deleted_ingestion_metrics: int = 0

    categories: list[PruneCategory] = field(default_factory=list)
    error_message: str | None = None
    status: str = "running"

    def as_serialisable_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible representation."""
        payload = asdict(self)
        payload["started_at"] = self.started_at.isoformat()
        return payload


def build_prune_plan(
    *,
    storage_profile: str,
    cert_storage_mode: str,
    hostname_retention_mode: str,
    cert_retention_days: int,
    observation_retention_days: int,
    entry_outcome_retention_days: int,
    metrics_retention_days: int,
    started_at: datetime,
    mode: str,
) -> PruneAggregate:
    """Construct the initial plan from active settings."""
    categories = [
        PruneCategory(name="certificates", retention_days=cert_retention_days),
        PruneCategory(name="observations", retention_days=observation_retention_days),
        PruneCategory(
            name="entry_outcomes", retention_days=entry_outcome_retention_days
        ),
        PruneCategory(name="ingestion_metrics", retention_days=metrics_retention_days),
    ]
    return PruneAggregate(
        storage_profile=storage_profile,
        cert_storage_mode=cert_storage_mode,
        hostname_retention_mode=hostname_retention_mode,
        started_at=started_at,
        mode=mode,
        categories=categories,
    )


def summarize_plan_for_console(aggregate: PruneAggregate) -> list[str]:
    """Build a list of console-ready lines describing *aggregate*."""
    lines = [
        "[bold]Storage Profile Prune Plan[/bold]",
        f"Active profile: [cyan]{aggregate.storage_profile}[/cyan]",
        f"Certificate storage mode: [cyan]{aggregate.cert_storage_mode}[/cyan]",
        f"Hostname retention: [cyan]{aggregate.hostname_retention_mode}[/cyan]",
        "",
        "Cutoffs:",
    ]
    for cat in aggregate.categories:
        if cat.is_disabled:
            lines.append(f"  {cat.name}: retain indefinitely (retention_days=0)")
        else:
            lines.append(f"  {cat.name}: older than {cat.retention_days} day(s)")
    lines.append("")
    if aggregate.mode == "dry_run":
        lines.append("Would delete:")
        for cat in aggregate.categories:
            if cat.is_disabled:
                continue
            lines.append(f"  {cat.name:<22} {cat.candidate_count:>12,}")
    else:
        lines.append("Deleted:")
        lines.append(f"  certificates           {aggregate.deleted_certificates:>12,}")
        lines.append(
            f"  certificate_hostnames  {aggregate.deleted_certificate_hostnames:>12,}"
        )
        lines.append(f"  ct_log_observations    {aggregate.deleted_observations:>12,}")
        lines.append(
            f"  ct_entry_outcomes      {aggregate.deleted_entry_outcomes:>12,}"
        )
        lines.append(
            f"  ingestion_metrics      {aggregate.deleted_ingestion_metrics:>12,}"
        )
    lines.append("")
    lines.append("Would preserve:")
    lines.append("  hostnames:                 preserved (always)")
    lines.append("  latest hostname summaries: preserved (always)")
    lines.append("  open audit findings:       preserved (always)")
    if aggregate.mode == "dry_run":
        lines.append("")
        lines.append("[yellow]Dry run only. Re-run with --execute to apply.[/yellow]")
    return lines


def summarize_plan_as_json(aggregate: PruneAggregate) -> dict[str, Any]:
    """Return a JSON-friendly dict for ``--json`` output."""
    return aggregate.as_serialisable_dict()
