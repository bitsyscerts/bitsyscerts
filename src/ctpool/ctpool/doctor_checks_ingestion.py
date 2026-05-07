"""Doctor ingestion-plane health checks (checks 1–7).

Each function returns a ``CheckResult`` and is independently testable.

Exports:
    check_migration_head      — (1) All migrations applied.
    check_log_discovery       — (2) CT log list reachable and non-empty.
    check_tail_lag            — (3) Tail cursors not too stale.
    check_disk_space          — (4) Free disk above thresholds.
    check_http_errors         — (5) HTTP error counts within thresholds.
    check_failed_ranges       — (6) No permanently-failed backfill ranges.
    check_stale_claims        — (7) No stale in-progress backfill claims.
"""

from __future__ import annotations

import shutil
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from ctpool.config import Settings
from ctpool.doctor_models import CheckResult, Severity
from ctpool.migration_runner import get_alembic_head, get_current_revision
from ctpool.models.log_backfill_range import CtLogBackfillRange


async def check_migration_head(settings: Settings) -> CheckResult:
    """Check (1): Current schema is at the Alembic head revision.

    Queries ``alembic_version`` and compares against the compiled head.

    Args:
        settings: Application settings (provides DB URL).
    """
    try:
        head = await get_alembic_head(settings)
        current = await get_current_revision(settings)
        if current != head:
            return CheckResult(
                name="migration_head",
                severity=Severity.CRITICAL,
                message=f"Schema at {current!r}; expected head {head!r}",
            )
        return CheckResult(
            name="migration_head",
            severity=Severity.OK,
            message=f"Schema is at head ({head})",
        )
    except Exception as exc:  # noqa: BLE001
        return CheckResult(
            name="migration_head",
            severity=Severity.CRITICAL,
            message="Schema is NOT at head or migration check failed",
            detail=str(exc),
        )


async def check_log_discovery(session: AsyncSession) -> CheckResult:
    """Check (2): At least one CT log is known and active.

    Args:
        session: Active async database session.
    """
    try:
        stmt = text("SELECT count(*) FROM ct_log_sources WHERE is_active = true")
        count = int((await session.execute(stmt)).scalar_one())
        if count == 0:
            return CheckResult(
                name="log_discovery",
                severity=Severity.WARNING,
                message="No active CT log sources found",
            )
        return CheckResult(
            name="log_discovery",
            severity=Severity.OK,
            message=f"{count} active CT log source(s)",
        )
    except Exception as exc:  # noqa: BLE001
        return CheckResult(
            name="log_discovery",
            severity=Severity.ERROR,
            message="Could not query CT log sources",
            detail=str(exc),
        )


async def check_tail_lag(
    session: AsyncSession,
    settings: Settings,
) -> CheckResult:
    """Check (3): Tail cursor lag is within configured thresholds.

    Lag is measured as seconds since the most-recently-updated log cursor.

    Args:
        session:  Active async database session.
        settings: Application settings (threshold values).
    """
    try:
        stmt = text(
            "SELECT EXTRACT(EPOCH FROM (now() - max(updated_at))) FROM ct_tail_cursors"
        )
        result = (await session.execute(stmt)).scalar_one()
        if result is None:
            return CheckResult(
                name="tail_lag",
                severity=Severity.WARNING,
                message="No tail cursors found",
            )
        lag_seconds = float(result)
        if lag_seconds >= settings.ct_doctor_tail_lag_critical_seconds:
            return CheckResult(
                name="tail_lag",
                severity=Severity.CRITICAL,
                message=(
                    f"Tail cursor lag {lag_seconds:.0f}s exceeds critical threshold "
                    f"({settings.ct_doctor_tail_lag_critical_seconds}s)"
                ),
            )
        if lag_seconds >= settings.ct_doctor_tail_lag_warning_seconds:
            return CheckResult(
                name="tail_lag",
                severity=Severity.WARNING,
                message=f"Tail cursor lag {lag_seconds:.0f}s exceeds warning threshold "
                f"({settings.ct_doctor_tail_lag_warning_seconds}s)",
            )
        return CheckResult(
            name="tail_lag",
            severity=Severity.OK,
            message=f"Tail cursor lag {lag_seconds:.0f}s OK",
        )
    except Exception as exc:  # noqa: BLE001
        return CheckResult(
            name="tail_lag",
            severity=Severity.ERROR,
            message="Could not query tail cursor lag",
            detail=str(exc),
        )


def check_disk_space(settings: Settings) -> CheckResult:
    """Check (4): Free disk space above configured thresholds.

    Uses ``shutil.disk_usage`` on ``settings.ct_disk_check_path``.

    Args:
        settings: Application settings (path and threshold values).
    """
    try:
        path = settings.ct_disk_check_path
        if not Path(path).exists():
            return CheckResult(
                name="disk_space",
                severity=Severity.WARNING,
                message=f"Disk check path does not exist: {path}",
            )
        usage = shutil.disk_usage(path)
        used_pct = 100.0 * usage.used / usage.total if usage.total else 0.0
        if used_pct >= settings.ct_doctor_disk_critical_pct:
            return CheckResult(
                name="disk_space",
                severity=Severity.CRITICAL,
                message=f"Disk usage {used_pct:.1f}% exceeds critical threshold "
                f"({settings.ct_doctor_disk_critical_pct:.0f}%)",
            )
        if used_pct >= settings.ct_doctor_disk_warning_pct:
            return CheckResult(
                name="disk_space",
                severity=Severity.WARNING,
                message=f"Disk usage {used_pct:.1f}% exceeds warning threshold "
                f"({settings.ct_doctor_disk_warning_pct:.0f}%)",
            )
        return CheckResult(
            name="disk_space",
            severity=Severity.OK,
            message=f"Disk usage {used_pct:.1f}% OK",
        )
    except Exception as exc:  # noqa: BLE001
        return CheckResult(
            name="disk_space",
            severity=Severity.ERROR,
            message="Could not check disk space",
            detail=str(exc),
        )


async def check_http_errors(
    session: AsyncSession,
    settings: Settings,
) -> CheckResult:
    """Check (5): HTTP error count within the metrics window.

    Inspects ``ingestion_metrics`` for recent HTTP error totals.

    Args:
        session:  Active async database session.
        settings: Application settings (threshold values).
    """
    try:
        stmt = text(
            "SELECT coalesce(sum(http_errors), 0) "
            "FROM ingestion_metrics "
            "WHERE recorded_at > now() - interval '1 hour'"
        )
        count = int((await session.execute(stmt)).scalar_one())
        if count >= settings.ct_doctor_http_error_critical:
            return CheckResult(
                name="http_errors",
                severity=Severity.CRITICAL,
                message=f"{count} HTTP error(s) in the last hour (critical >= "
                f"{settings.ct_doctor_http_error_critical})",
            )
        if count >= settings.ct_doctor_http_error_warning:
            return CheckResult(
                name="http_errors",
                severity=Severity.WARNING,
                message=f"{count} HTTP error(s) in the last hour",
            )
        return CheckResult(
            name="http_errors",
            severity=Severity.OK,
            message=f"{count} HTTP error(s) in the last hour",
        )
    except Exception as exc:  # noqa: BLE001
        return CheckResult(
            name="http_errors",
            severity=Severity.ERROR,
            message="Could not query HTTP error metrics",
            detail=str(exc),
        )


async def check_failed_ranges(session: AsyncSession) -> CheckResult:
    """Check (6): No backfill ranges are in a permanently-failed state.

    Args:
        session: Active async database session.
    """
    try:
        stmt = (
            select(func.count())
            .select_from(CtLogBackfillRange)
            .where(CtLogBackfillRange.status == "failed")
        )
        count = int((await session.execute(stmt)).scalar_one())
        if count > 0:
            return CheckResult(
                name="failed_ranges",
                severity=Severity.CRITICAL,
                message=f"{count} backfill range(s) in 'failed' status",
            )
        return CheckResult(
            name="failed_ranges",
            severity=Severity.OK,
            message="No failed backfill ranges",
        )
    except Exception as exc:  # noqa: BLE001
        return CheckResult(
            name="failed_ranges",
            severity=Severity.ERROR,
            message="Could not query backfill range statuses",
            detail=str(exc),
        )


async def check_stale_claims(
    session: AsyncSession,
    settings: Settings,
) -> CheckResult:
    """Check (7): No backfill ranges are stale in-progress claims.

    A claim is stale if it has status 'in_progress' and heartbeat_at is older
    than ``ct_backfill_claim_timeout_seconds``.

    Args:
        session:  Active async database session.
        settings: Application settings (claim timeout).
    """
    try:
        cutoff = datetime.now(UTC) - timedelta(
            seconds=settings.ct_backfill_claim_timeout_seconds
        )
        stmt = (
            select(func.count())
            .select_from(CtLogBackfillRange)
            .where(CtLogBackfillRange.status == "in_progress")
            .where(CtLogBackfillRange.heartbeat_at < cutoff)
        )
        count = int((await session.execute(stmt)).scalar_one())
        if count > 0:
            return CheckResult(
                name="stale_claims",
                severity=Severity.WARNING,
                message=f"{count} stale in-progress backfill claim(s)",
            )
        return CheckResult(
            name="stale_claims",
            severity=Severity.OK,
            message="No stale backfill claims",
        )
    except Exception as exc:  # noqa: BLE001
        return CheckResult(
            name="stale_claims",
            severity=Severity.ERROR,
            message="Could not query backfill claim staleness",
            detail=str(exc),
        )
