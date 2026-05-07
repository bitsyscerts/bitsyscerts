"""Progress and summary reporting for the prune-expired-certs command.

Exports:
    PruneSummary    — Accumulated totals from a prune run.
    PruneReporter   — Emits Rich-formatted progress and summary to a console.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from rich.console import Console
from rich.table import Table


@dataclass
class PruneSummary:
    """Accumulated row counts from a complete prune-expired-certs execution."""

    mode: str
    retention_days: int
    cutoff: datetime
    candidate_certificates: int = 0
    blocked_latest_certificates: int = 0
    blocked_missing_summary: int = 0
    deleted_certificates: int = 0
    deleted_certificate_hostnames: int = 0
    deleted_ct_observations: int = 0
    batches_processed: int = 0
    status: str = "running"
    error_message: str | None = None


class PruneReporter:
    """Rich-formatted progress reporter for the prune-expired-certs command."""

    def __init__(self, console: Console) -> None:
        self._console = console

    def announce(self, summary: PruneSummary) -> None:
        """Print the run parameters before work begins."""
        label = (
            "[yellow]DRY RUN[/yellow]"
            if summary.mode == "dry_run"
            else "[red]EXECUTE[/red]"
        )
        self._console.print(
            f"\nprune-expired-certs  {label}  "
            f"retention=[cyan]{summary.retention_days}[/cyan] days  "
            f"cutoff=[cyan]{summary.cutoff.date()}[/cyan]\n"
        )

    def batch_progress(self, summary: PruneSummary) -> None:
        """Print an in-place progress line after each batch."""
        self._console.print(
            f"  batch {summary.batches_processed:>4}  "
            f"deleted {summary.deleted_certificates:,} certs  "
            f"({summary.deleted_ct_observations:,} obs / "
            f"{summary.deleted_certificate_hostnames:,} joins)",
            end="\r",
        )

    def print_summary(self, summary: PruneSummary) -> None:
        """Print the final summary table."""
        self._console.print()  # newline after progress line
        t = Table(title="Prune Run Summary", show_lines=False)
        t.add_column("Metric", style="bold")
        t.add_column("Value", justify="right")
        t.add_row("Mode", summary.mode)
        t.add_row("Retention days", str(summary.retention_days))
        t.add_row("Cutoff", str(summary.cutoff.date()))
        t.add_row("Candidate certs", f"{summary.candidate_certificates:,}")
        t.add_row("Blocked (latest cert)", f"{summary.blocked_latest_certificates:,}")
        t.add_row("Blocked (no summary)", f"{summary.blocked_missing_summary:,}")
        t.add_row("Deleted certs", f"{summary.deleted_certificates:,}")
        t.add_row(
            "Deleted cert-hostname joins", f"{summary.deleted_certificate_hostnames:,}"
        )
        t.add_row("Deleted observations", f"{summary.deleted_ct_observations:,}")
        t.add_row("Batches", str(summary.batches_processed))
        status_style = "green" if summary.status == "complete" else "red"
        t.add_row("Status", f"[{status_style}]{summary.status}[/{status_style}]")
        if summary.error_message:
            t.add_row("Error", summary.error_message)
        self._console.print(t)
