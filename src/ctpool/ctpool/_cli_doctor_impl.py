"""Implementation for the ctpool doctor CLI command.

Exports:
    run_doctor_command — Execute all health checks, print report, and return exit code.
"""

from __future__ import annotations

from rich.console import Console

from ctpool.config import get_settings
from ctpool.doctor_models import Severity
from ctpool.doctor_reporter import DoctorReporter
from ctpool.doctor_runner import run_doctor

# Exit codes
EXIT_OK = 0
EXIT_CRITICAL = 1
EXIT_ERROR = 2


async def run_doctor_command(
    *,
    strict: bool = False,
    json_output: bool = False,
    expect_workers: bool = False,
    console: Console,
) -> int:
    """Execute all doctor checks, render the report, and return an exit code.

    Exit codes:
        0 — all checks OK or WARNING (unless --strict).
        1 — one or more CRITICAL checks.
        2 — one or more ERROR checks (or CRITICAL in strict mode).

    Args:
        strict:         Exit non-zero even for WARNING severity.
        json_output:    Print JSON instead of the Rich table.
        expect_workers: Treat stale metrics as a WARNING.
        console:        Rich console for output.

    Returns:
        Integer exit code.
    """
    settings = get_settings()
    report = await run_doctor(settings, expect_workers=expect_workers)
    reporter = DoctorReporter(console)

    if json_output:
        reporter.print_json(report)
    else:
        reporter.print_human(report)

    overall = report.overall_severity
    if overall >= Severity.ERROR:
        return EXIT_ERROR
    if overall >= Severity.CRITICAL:
        return EXIT_CRITICAL
    if strict and overall >= Severity.WARNING:
        return EXIT_CRITICAL
    return EXIT_OK
