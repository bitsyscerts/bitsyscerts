"""Reporting for the ctpool doctor command.

Exports:
    DoctorReporter — Rich (human) and JSON output for a DoctorReport.
"""

from __future__ import annotations

import json

from rich.console import Console
from rich.table import Table

from ctpool.doctor_models import DoctorReport, Severity

_SEVERITY_STYLE: dict[Severity, str] = {
    Severity.OK: "green",
    Severity.WARNING: "yellow",
    Severity.CRITICAL: "red bold",
    Severity.ERROR: "red italic",
}


class DoctorReporter:
    """Renders a DoctorReport to a Rich console or as JSON."""

    def __init__(self, console: Console) -> None:
        self._console = console

    def print_human(self, report: DoctorReport) -> None:
        """Print a Rich-formatted table of all check results.

        Args:
            report: Completed doctor report.
        """
        t = Table(title="ctpool doctor", show_lines=False)
        t.add_column("Check", style="bold")
        t.add_column("Severity")
        t.add_column("Message")
        t.add_column("Detail")
        for check in report.checks:
            style = _SEVERITY_STYLE.get(check.severity, "")
            t.add_row(
                check.name,
                f"[{style}]{check.severity.name}[/{style}]",
                check.message,
                check.detail or "",
            )
        self._console.print(t)
        overall = report.overall_severity
        overall_style = _SEVERITY_STYLE.get(overall, "")
        self._console.print(
            f"\nOverall: [{overall_style}]{overall.name}[/{overall_style}]"
        )

    def print_json(self, report: DoctorReport) -> None:
        """Print a JSON representation of all check results to stdout.

        Args:
            report: Completed doctor report.
        """
        payload = {
            "overall": report.overall_severity.name,
            "checks": [
                {
                    "name": c.name,
                    "severity": c.severity.name,
                    "message": c.message,
                    "detail": c.detail,
                }
                for c in report.checks
            ],
        }
        print(json.dumps(payload, indent=2))
