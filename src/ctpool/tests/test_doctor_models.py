"""Unit tests for ctpool.doctor_models.

Covers:
    - Severity ordering
    - CheckResult creation
    - DoctorReport aggregation (overall_severity, is_healthy, add)
"""

from __future__ import annotations

from ctpool.doctor_models import CheckResult, DoctorReport, Severity

# ---------------------------------------------------------------------------
# Severity ordering
# ---------------------------------------------------------------------------


def test_severity_ordering():
    assert Severity.OK < Severity.WARNING < Severity.CRITICAL < Severity.ERROR


def test_severity_max():
    sev = max([Severity.OK, Severity.CRITICAL, Severity.WARNING])
    assert sev == Severity.CRITICAL


# ---------------------------------------------------------------------------
# CheckResult
# ---------------------------------------------------------------------------


def test_check_result_ok():
    r = CheckResult(name="disk_space", severity=Severity.OK, message="OK")
    assert r.name == "disk_space"
    assert r.detail is None


def test_check_result_with_detail():
    r = CheckResult(
        name="migration_head",
        severity=Severity.CRITICAL,
        message="Schema out of date",
        detail="expected xyz got abc",
    )
    assert r.detail == "expected xyz got abc"


# ---------------------------------------------------------------------------
# DoctorReport
# ---------------------------------------------------------------------------


def test_empty_report_is_ok():
    report = DoctorReport()
    assert report.overall_severity == Severity.OK
    assert report.is_healthy is True


def test_report_single_ok():
    report = DoctorReport()
    report.add(CheckResult("a", Severity.OK, "fine"))
    assert report.overall_severity == Severity.OK
    assert report.is_healthy is True


def test_report_warning_is_healthy():
    report = DoctorReport()
    report.add(CheckResult("a", Severity.OK, "fine"))
    report.add(CheckResult("b", Severity.WARNING, "watch out"))
    assert report.overall_severity == Severity.WARNING
    assert report.is_healthy is True


def test_report_critical_is_not_healthy():
    report = DoctorReport()
    report.add(CheckResult("a", Severity.OK, "fine"))
    report.add(CheckResult("b", Severity.CRITICAL, "broken"))
    assert report.overall_severity == Severity.CRITICAL
    assert report.is_healthy is False


def test_report_error_is_not_healthy():
    report = DoctorReport()
    report.add(CheckResult("x", Severity.ERROR, "exception"))
    assert report.overall_severity == Severity.ERROR
    assert report.is_healthy is False


def test_report_overall_severity_is_max():
    report = DoctorReport()
    report.add(CheckResult("a", Severity.OK, "ok"))
    report.add(CheckResult("b", Severity.WARNING, "warn"))
    report.add(CheckResult("c", Severity.CRITICAL, "crit"))
    assert report.overall_severity == Severity.CRITICAL
    assert len(report.checks) == 3
