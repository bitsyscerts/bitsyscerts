"""Data models for the ctpool doctor command.

Exports:
    Severity      — Ordered check severity enum.
    CheckResult   — Single health-check outcome.
    DoctorReport  — Aggregated report across all checks.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum


class Severity(IntEnum):
    """Ordered severity levels for doctor checks.

    Higher values are more severe.  The overall report severity is the
    maximum of all individual check severities.
    """

    OK = 0
    WARNING = 1
    CRITICAL = 2
    ERROR = 3


@dataclass(frozen=True)
class CheckResult:
    """Result of one doctor health check."""

    name: str
    severity: Severity
    message: str
    detail: str | None = None


@dataclass
class DoctorReport:
    """Aggregated results from all doctor checks."""

    checks: list[CheckResult] = field(default_factory=list)

    @property
    def overall_severity(self) -> Severity:
        """Highest severity across all checks, or OK if no checks ran."""
        if not self.checks:
            return Severity.OK
        return max(c.severity for c in self.checks)

    @property
    def is_healthy(self) -> bool:
        """True if no check is CRITICAL or ERROR."""
        return self.overall_severity < Severity.CRITICAL

    def add(self, result: CheckResult) -> None:
        """Append a check result to the report."""
        self.checks.append(result)
