"""Orchestrator for the ctpool doctor command.

Exports:
    run_doctor — Execute all health checks and return a DoctorReport.
"""

from __future__ import annotations

from ctpool.config import Settings
from ctpool.db import create_engine, create_session_factory
from ctpool.doctor_checks_health import (
    check_cert_count,
    check_entry_outcomes_backlog,
    check_hostname_count,
    check_metrics_freshness,
    check_observation_orphans,
    check_open_audit_findings,
    check_prune_run_health,
)
from ctpool.doctor_checks_ingestion import (
    check_disk_space,
    check_failed_ranges,
    check_http_errors,
    check_log_discovery,
    check_migration_head,
    check_stale_claims,
    check_tail_lag,
)
from ctpool.doctor_models import DoctorReport


async def run_doctor(
    settings: Settings,
    *,
    expect_workers: bool = False,
) -> DoctorReport:
    """Execute all 14 doctor health checks and return an aggregated report.

    Checks are grouped into two passes:
    - Pass 1: Checks that do not require a database session (e.g. disk space).
    - Pass 2: Checks that query the live database.

    Args:
        settings:       Application settings.
        expect_workers: If True, treat stale metrics as WARNING (not info).

    Returns:
        A DoctorReport containing one CheckResult per check.
    """
    report = DoctorReport()

    # Pass 1: no-DB checks
    report.add(check_disk_space(settings))
    report.add(await check_migration_head(settings))

    # Pass 2: database checks
    engine = create_engine(settings)
    factory = create_session_factory(engine)
    async with factory() as session:
        report.add(await check_log_discovery(session))
        report.add(await check_tail_lag(session, settings))
        report.add(await check_http_errors(session, settings))
        report.add(await check_failed_ranges(session))
        report.add(await check_stale_claims(session, settings))
        report.add(await check_hostname_count(session))
        report.add(await check_cert_count(session))
        report.add(await check_open_audit_findings(session))
        report.add(await check_metrics_freshness(session, settings, expect_workers))
        report.add(await check_entry_outcomes_backlog(session))
        report.add(await check_prune_run_health(session))
        report.add(await check_observation_orphans(session))

    return report
