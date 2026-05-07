"""Unit tests for _cli_check_audit_impl and _cli_repair_audit_impl helpers.

Tests for pure/stateless functions that do not need a live database.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from ctpool._cli_check_audit_impl import _print_results
from ctpool._cli_repair_audit_impl import (
    _print_repair_line,
    _print_summary,
    _resolve_severities,
)
from ctpool.audit_checker import AuditCheckResult
from ctpool.audit_constants import (
    DEFAULT_REPAIR_SEVERITIES,
    FINDING_TYPE_STALE_BACKFILL_CLAIM,
    SEVERITY_ERROR,
    SEVERITY_WARNING,
)


def _make_console() -> MagicMock:
    """Return a MagicMock console that records printed lines."""
    console = MagicMock()
    console.printed: list[str] = []

    def _print(msg: str) -> None:
        console.printed.append(msg)

    console.print = MagicMock(side_effect=_print)
    return console


# ---------------------------------------------------------------------------
# _print_results (no findings)
# ---------------------------------------------------------------------------


def test_print_results_no_findings_prints_clean_message() -> None:
    """_print_results prints a green 'no findings' message when total is 0."""
    result = AuditCheckResult()
    console = _make_console()
    _print_results(result, dry_run=False, console=console)
    assert console.print.call_count == 1
    msg = console.print.call_args[0][0]
    assert "No new audit findings" in msg


def test_print_results_with_findings_prints_totals() -> None:
    """_print_results prints per-type counts when findings are present."""
    result = AuditCheckResult(stale_claims=1, failed_ranges=2)
    console = _make_console()
    _print_results(result, dry_run=False, console=console)
    all_text = " ".join(c[0][0] for c in console.print.call_args_list)
    assert "3 total" in all_text
    assert "stale_backfill_claim" in all_text
    assert "failed_backfill_range" in all_text


def test_print_results_dry_run_adds_prefix() -> None:
    """_print_results includes DRY RUN prefix when dry_run=True."""
    result = AuditCheckResult(missing_outcomes=1)
    console = _make_console()
    _print_results(result, dry_run=True, console=console)
    all_text = " ".join(c[0][0] for c in console.print.call_args_list)
    assert "DRY RUN" in all_text


def test_print_results_missing_observations_shown() -> None:
    """_print_results shows missing_observations count when non-zero."""
    result = AuditCheckResult(missing_observations=3)
    console = _make_console()
    _print_results(result, dry_run=False, console=console)
    all_text = " ".join(c[0][0] for c in console.print.call_args_list)
    assert "missing_observations_without_outcome" in all_text


# ---------------------------------------------------------------------------
# _resolve_severities
# ---------------------------------------------------------------------------


def test_resolve_severities_default_returns_default_set() -> None:
    """_resolve_severities returns DEFAULT_REPAIR_SEVERITIES when no filter."""
    result = _resolve_severities(None, include_warnings=False)
    assert result == DEFAULT_REPAIR_SEVERITIES


def test_resolve_severities_include_warnings_adds_warning() -> None:
    """_resolve_severities adds warning severity when include_warnings=True."""
    result = _resolve_severities(None, include_warnings=True)
    assert SEVERITY_WARNING in result


def test_resolve_severities_explicit_filter_overrides_defaults() -> None:
    """_resolve_severities uses explicit comma-separated filter over defaults."""
    result = _resolve_severities("error", include_warnings=False)
    assert result == frozenset({SEVERITY_ERROR})


def test_resolve_severities_unknown_raises_value_error() -> None:
    """_resolve_severities raises ValueError for unknown severity names."""
    with pytest.raises(ValueError, match="Unknown severities"):
        _resolve_severities("legendary", include_warnings=False)


# ---------------------------------------------------------------------------
# _print_repair_line and _print_summary
# ---------------------------------------------------------------------------


def test_print_repair_line_includes_finding_info() -> None:
    """_print_repair_line prints id, type, status, and action."""
    finding = MagicMock()
    finding.id = "abc-123"
    finding.finding_type = FINDING_TYPE_STALE_BACKFILL_CLAIM
    finding.status = "resolved"
    finding.repair_action = "retry"
    console = _make_console()
    _print_repair_line(finding, dry_run=False, console=console)
    msg = console.print.call_args[0][0]
    assert "abc-123" in msg
    assert FINDING_TYPE_STALE_BACKFILL_CLAIM in msg
    assert "resolved" in msg
    assert "retry" in msg


def test_print_repair_line_dry_run_prefix() -> None:
    """_print_repair_line includes DRY RUN prefix when dry_run=True."""
    finding = MagicMock()
    console = _make_console()
    _print_repair_line(finding, dry_run=True, console=console)
    msg = console.print.call_args[0][0]
    assert "DRY RUN" in msg


def test_print_summary_dry_run_message() -> None:
    """_print_summary says 'Dry-run processed' when dry_run=True."""
    console = _make_console()
    _print_summary(5, errors=0, dry_run=True, console=console)
    msg = console.print.call_args[0][0]
    assert "Dry-run processed" in msg
    assert "5" in msg


def test_print_summary_non_dry_run_message() -> None:
    """_print_summary says 'Repaired' when dry_run=False."""
    console = _make_console()
    _print_summary(3, errors=0, dry_run=False, console=console)
    msg = console.print.call_args[0][0]
    assert "Repaired" in msg
    assert "3" in msg


def test_print_summary_shows_error_count() -> None:
    """_print_summary prints an error line when errors > 0."""
    console = _make_console()
    _print_summary(2, errors=1, dry_run=False, console=console)
    all_text = " ".join(c[0][0] for c in console.print.call_args_list)
    assert "Failed" in all_text
    assert "1" in all_text
