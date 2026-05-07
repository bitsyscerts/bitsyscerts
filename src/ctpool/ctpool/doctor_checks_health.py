"""Doctor data-health checks (checks 8–14).

Each function returns a ``CheckResult`` and is independently testable.

Exports:
    check_hostname_count         — (8)  Non-zero hostname count.
    check_cert_count             — (9)  Non-zero certificate count.
    check_open_audit_findings    — (10) No open CRITICAL audit findings.
    check_metrics_freshness      — (11) Recent ingestion_metrics rows exist.
    check_entry_outcomes_backlog — (12) No large unprocessed outcome backlog.
    check_prune_run_health       — (13) Most recent prune run completed OK.
    check_observation_orphans    — (14) Orphaned observations within tolerance.
"""

from __future__ import annotations

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from ctpool.config import Settings
from ctpool.doctor_models import CheckResult, Severity
from ctpool.models.certificate import Certificate
from ctpool.models.hostname import Hostname

_OUTCOMES_BACKLOG_WARNING: int = 500_000
_OUTCOMES_BACKLOG_CRITICAL: int = 5_000_000
_ORPHAN_RATIO_WARNING: float = 0.05
_ORPHAN_RATIO_CRITICAL: float = 0.20


async def check_hostname_count(session: AsyncSession) -> CheckResult:
    """Check (8): At least one hostname has been ingested.

    Args:
        session: Active async database session.
    """
    try:
        count = int(
            (
                await session.execute(select(func.count()).select_from(Hostname))
            ).scalar_one()
        )
        if count == 0:
            return CheckResult(
                name="hostname_count",
                severity=Severity.WARNING,
                message="No hostnames found — ingestion may not have run yet",
            )
        return CheckResult(
            name="hostname_count",
            severity=Severity.OK,
            message=f"{count:,} hostname(s) ingested",
        )
    except Exception as exc:  # noqa: BLE001
        return CheckResult(
            name="hostname_count",
            severity=Severity.ERROR,
            message="Could not query hostname count",
            detail=str(exc),
        )


async def check_cert_count(session: AsyncSession) -> CheckResult:
    """Check (9): At least one certificate has been stored.

    Args:
        session: Active async database session.
    """
    try:
        count = int(
            (
                await session.execute(select(func.count()).select_from(Certificate))
            ).scalar_one()
        )
        if count == 0:
            return CheckResult(
                name="cert_count",
                severity=Severity.WARNING,
                message="No certificates found — ingestion may not have run yet",
            )
        return CheckResult(
            name="cert_count",
            severity=Severity.OK,
            message=f"{count:,} certificate(s) stored",
        )
    except Exception as exc:  # noqa: BLE001
        return CheckResult(
            name="cert_count",
            severity=Severity.ERROR,
            message="Could not query certificate count",
            detail=str(exc),
        )


async def check_open_audit_findings(session: AsyncSession) -> CheckResult:
    """Check (10): No CRITICAL-severity open audit findings.

    Args:
        session: Active async database session.
    """
    try:
        stmt = text(
            "SELECT count(*) FROM ct_audit_findings "
            "WHERE status = 'open' AND severity = 'critical'"
        )
        count = int((await session.execute(stmt)).scalar_one())
        if count > 0:
            return CheckResult(
                name="open_audit_findings",
                severity=Severity.CRITICAL,
                message=f"{count} open CRITICAL audit finding(s)",
            )
        return CheckResult(
            name="open_audit_findings",
            severity=Severity.OK,
            message="No open critical audit findings",
        )
    except Exception as exc:  # noqa: BLE001
        return CheckResult(
            name="open_audit_findings",
            severity=Severity.ERROR,
            message="Could not query audit findings",
            detail=str(exc),
        )


async def check_metrics_freshness(
    session: AsyncSession,
    settings: Settings,
    expect_workers: bool = False,
) -> CheckResult:
    """Check (11): Recent ingestion_metrics rows exist.

    If ``expect_workers`` is True, the check is WARNING if stale; otherwise
    it is only informational.

    Args:
        session:        Active async database session.
        settings:       Application settings (stale threshold).
        expect_workers: Treat staleness as a WARNING (not just INFO).
    """
    try:
        stmt = text(
            "SELECT EXTRACT(EPOCH FROM (now() - max(recorded_at))) "
            "FROM ingestion_metrics"
        )
        result = (await session.execute(stmt)).scalar_one()
        if result is None:
            sev = Severity.WARNING if expect_workers else Severity.OK
            return CheckResult(
                name="metrics_freshness",
                severity=sev,
                message="No ingestion_metrics rows found",
            )
        age_seconds = float(result)
        if age_seconds >= settings.ct_doctor_metrics_stale_warning_seconds:
            sev = Severity.WARNING if expect_workers else Severity.OK
            return CheckResult(
                name="metrics_freshness",
                severity=sev,
                message=f"Most-recent ingestion_metrics row is {age_seconds:.0f}s old",
            )
        return CheckResult(
            name="metrics_freshness",
            severity=Severity.OK,
            message=f"Most-recent ingestion_metrics row is {age_seconds:.0f}s old",
        )
    except Exception as exc:  # noqa: BLE001
        return CheckResult(
            name="metrics_freshness",
            severity=Severity.ERROR,
            message="Could not query ingestion_metrics freshness",
            detail=str(exc),
        )


async def check_entry_outcomes_backlog(session: AsyncSession) -> CheckResult:
    """Check (12): ct_entry_outcomes backlog is within tolerance.

    A large backlog may indicate stalled re-processing.

    Args:
        session: Active async database session.
    """
    try:
        stmt = text("SELECT count(*) FROM ct_entry_outcomes WHERE outcome = 'pending'")
        count = int((await session.execute(stmt)).scalar_one())
        if count >= _OUTCOMES_BACKLOG_CRITICAL:
            return CheckResult(
                name="outcomes_backlog",
                severity=Severity.CRITICAL,
                message=(
                    f"{count:,} pending outcome rows"
                    f" (critical >= {_OUTCOMES_BACKLOG_CRITICAL:,})"
                ),
            )
        if count >= _OUTCOMES_BACKLOG_WARNING:
            return CheckResult(
                name="outcomes_backlog",
                severity=Severity.WARNING,
                message=f"{count:,} pending outcome rows",
            )
        return CheckResult(
            name="outcomes_backlog",
            severity=Severity.OK,
            message=f"{count:,} pending outcome rows",
        )
    except Exception as exc:  # noqa: BLE001
        return CheckResult(
            name="outcomes_backlog",
            severity=Severity.ERROR,
            message="Could not query entry outcomes backlog",
            detail=str(exc),
        )


async def check_prune_run_health(session: AsyncSession) -> CheckResult:
    """Check (13): Most recent prune run completed successfully.

    Args:
        session: Active async database session.
    """
    try:
        stmt = text(
            "SELECT status, error_message "
            "FROM ct_prune_runs "
            "ORDER BY started_at DESC "
            "LIMIT 1"
        )
        row = (await session.execute(stmt)).first()
        if row is None:
            return CheckResult(
                name="prune_run_health",
                severity=Severity.OK,
                message="No prune runs recorded yet",
            )
        status, error_message = row
        if status == "failed":
            return CheckResult(
                name="prune_run_health",
                severity=Severity.WARNING,
                message="Most recent prune run failed",
                detail=error_message,
            )
        return CheckResult(
            name="prune_run_health",
            severity=Severity.OK,
            message=f"Most recent prune run: {status}",
        )
    except Exception as exc:  # noqa: BLE001
        return CheckResult(
            name="prune_run_health",
            severity=Severity.ERROR,
            message="Could not query prune run status",
            detail=str(exc),
        )


async def check_observation_orphans(session: AsyncSession) -> CheckResult:
    """Check (14): Orphaned ct_log_observations are within tolerance.

    Orphans are rows where certificate_id references a certificate that was
    deleted (or is NULL).  A small ratio is acceptable; a large ratio is not.

    Args:
        session: Active async database session.
    """
    try:
        stmt = text(
            """
            SELECT
                count(*) FILTER (WHERE certificate_id IS NULL) AS null_certs,
                count(*) AS total
            FROM ct_log_observations
            """
        )
        row = (await session.execute(stmt)).one()
        null_count, total = int(row[0]), int(row[1])
        if total == 0:
            return CheckResult(
                name="observation_orphans",
                severity=Severity.OK,
                message="No observations to check",
            )
        ratio = null_count / total
        if ratio >= _ORPHAN_RATIO_CRITICAL:
            return CheckResult(
                name="observation_orphans",
                severity=Severity.CRITICAL,
                message=(
                    f"{null_count:,}/{total:,} observations ({ratio:.1%}) have no cert"
                ),
            )
        if ratio >= _ORPHAN_RATIO_WARNING:
            return CheckResult(
                name="observation_orphans",
                severity=Severity.WARNING,
                message=(
                    f"{null_count:,}/{total:,} observations ({ratio:.1%}) have no cert"
                ),
            )
        return CheckResult(
            name="observation_orphans",
            severity=Severity.OK,
            message=f"{null_count:,}/{total:,} observations without cert",
        )
    except Exception as exc:  # noqa: BLE001
        return CheckResult(
            name="observation_orphans",
            severity=Severity.ERROR,
            message="Could not query observation orphans",
            detail=str(exc),
        )
