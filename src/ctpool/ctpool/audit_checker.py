"""Maps raw audit query rows into CtAuditFinding ORM objects and persists them.

Deduplication strategy: one open finding per (log_source_id, finding_type,
start_index, end_index, range_id).  Existing open findings for the same key
are skipped rather than duplicated.

Exports:
    run_stale_backfill_claim_check      — Detect stale in_progress ranges.
    run_failed_backfill_range_check     — Detect failed ranges.
    run_missing_entry_outcomes_check    — Detect index gaps in completed ranges.
    run_missing_observations_check      — Detect observations without outcomes.
    run_all_checks                      — Run all four checks and return totals.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.engine import RowMapping
from sqlalchemy.ext.asyncio import AsyncSession

from ctpool.audit_constants import (
    FINDING_TYPE_FAILED_BACKFILL_RANGE,
    FINDING_TYPE_MISSING_ENTRY_OUTCOMES,
    FINDING_TYPE_MISSING_OBSERVATIONS_WITHOUT_OUTCOME,
    FINDING_TYPE_STALE_BACKFILL_CLAIM,
    SEVERITY_ERROR,
    SEVERITY_WARNING,
    STATUS_OPEN,
)
from ctpool.audit_queries import (
    query_failed_backfill_ranges,
    query_missing_entry_outcomes,
    query_missing_observations_without_outcome,
    query_stale_backfill_claims,
)
from ctpool.models.audit_finding import CtAuditFinding

_logger = logging.getLogger(__name__)


@dataclass
class AuditCheckResult:
    """Totals from a single audit check pass."""

    stale_claims: int = 0
    failed_ranges: int = 0
    missing_outcomes: int = 0
    missing_observations: int = 0

    @property
    def total_new_findings(self) -> int:
        """Sum of all new findings inserted across all check types."""
        return (
            self.stale_claims
            + self.failed_ranges
            + self.missing_outcomes
            + self.missing_observations
        )


async def _existing_open_keys(
    session: AsyncSession,
    finding_type: str,
) -> set[tuple[str | None, str | None, int | None, int | None]]:
    """Return a set of (log_source_id, range_id, start_index, end_index) tuples
    for all open findings of the given type, used for deduplication."""
    rows = await session.execute(
        select(
            CtAuditFinding.log_source_id,
            CtAuditFinding.range_id,
            CtAuditFinding.start_index,
            CtAuditFinding.end_index,
        ).where(
            CtAuditFinding.finding_type == finding_type,
            CtAuditFinding.status == STATUS_OPEN,
        )
    )
    return {
        (
            str(r.log_source_id) if r.log_source_id else None,
            str(r.range_id) if r.range_id else None,
            r.start_index,
            r.end_index,
        )
        for r in rows
    }


async def run_stale_backfill_claim_check(
    session: AsyncSession,
    claim_timeout_seconds: int,
) -> int:
    """Detect stale in_progress ranges and create open findings for each."""
    rows = await query_stale_backfill_claims(session, claim_timeout_seconds)
    existing = await _existing_open_keys(session, FINDING_TYPE_STALE_BACKFILL_CLAIM)
    count = 0
    for row in rows:
        key = _range_key(row)
        if key in existing:
            continue
        session.add(
            CtAuditFinding(
                log_source_id=row["log_source_id"],
                finding_type=FINDING_TYPE_STALE_BACKFILL_CLAIM,
                severity=SEVERITY_WARNING,
                status=STATUS_OPEN,
                range_id=row["id"],
                start_index=row["start_index"],
                end_index=row["end_index"],
                details_json={
                    "claimed_by": row["claimed_by"],
                    "heartbeat_at": _dt_str(row.get("heartbeat_at")),
                },
            )
        )
        count += 1
    await session.flush()
    return count


async def run_failed_backfill_range_check(
    session: AsyncSession,
) -> int:
    """Detect failed backfill ranges and create open error findings."""
    rows = await query_failed_backfill_ranges(session)
    existing = await _existing_open_keys(session, FINDING_TYPE_FAILED_BACKFILL_RANGE)
    count = 0
    for row in rows:
        key = _range_key(row)
        if key in existing:
            continue
        session.add(
            CtAuditFinding(
                log_source_id=row["log_source_id"],
                finding_type=FINDING_TYPE_FAILED_BACKFILL_RANGE,
                severity=SEVERITY_ERROR,
                status=STATUS_OPEN,
                range_id=row["id"],
                start_index=row["start_index"],
                end_index=row["end_index"],
                details_json={
                    "last_error": row.get("last_error"),
                    "attempt_count": row.get("attempt_count"),
                    "range_kind": row.get("range_kind"),
                },
            )
        )
        count += 1
    await session.flush()
    return count


async def run_missing_entry_outcomes_check(
    session: AsyncSession,
) -> int:
    """Detect completed ranges with missing outcome rows."""
    rows = await query_missing_entry_outcomes(session)
    existing = await _existing_open_keys(session, FINDING_TYPE_MISSING_ENTRY_OUTCOMES)
    count = 0
    for row in rows:
        key = _range_key_from_outcomes_row(row)
        if key in existing:
            continue
        session.add(
            CtAuditFinding(
                log_source_id=row["log_source_id"],
                finding_type=FINDING_TYPE_MISSING_ENTRY_OUTCOMES,
                severity=SEVERITY_ERROR,
                status=STATUS_OPEN,
                range_id=row["range_id"],
                start_index=row["start_index"],
                end_index=row["end_index"],
                missing_count=row["missing_count"],
                details_json={
                    "expected_count": row["expected_count"],
                    "actual_count": row["actual_count"],
                },
            )
        )
        count += 1
    await session.flush()
    return count


async def run_missing_observations_check(
    session: AsyncSession,
) -> int:
    """Detect ct_log_observations rows that have no corresponding outcome row."""
    rows = await query_missing_observations_without_outcome(session)
    existing = await _existing_open_keys(
        session, FINDING_TYPE_MISSING_OBSERVATIONS_WITHOUT_OUTCOME
    )
    count = 0
    for row in rows:
        key = _obs_key(row)
        if key in existing:
            continue
        session.add(
            CtAuditFinding(
                log_source_id=row["log_source_id"],
                finding_type=FINDING_TYPE_MISSING_OBSERVATIONS_WITHOUT_OUTCOME,
                severity=SEVERITY_WARNING,
                status=STATUS_OPEN,
                start_index=row["log_index"],
                end_index=row["log_index"],
                details_json={"observation_id": str(row["observation_id"])},
            )
        )
        count += 1
    await session.flush()
    return count


async def run_all_checks(
    session: AsyncSession,
    claim_timeout_seconds: int,
) -> AuditCheckResult:
    """Run all four audit checks and return per-type new-finding counts.

    Each check runs in its own savepoint so a failure in one check does not
    prevent the remaining checks from running or poison the session state.
    """
    result = AuditCheckResult()

    sp = await session.begin_nested()
    try:
        result.stale_claims = await run_stale_backfill_claim_check(
            session, claim_timeout_seconds
        )
        await sp.commit()
    except Exception:
        await sp.rollback()
        _logger.exception("stale-claims audit check failed")

    sp = await session.begin_nested()
    try:
        result.failed_ranges = await run_failed_backfill_range_check(session)
        await sp.commit()
    except Exception:
        await sp.rollback()
        _logger.exception("failed-ranges audit check failed")

    sp = await session.begin_nested()
    try:
        result.missing_outcomes = await run_missing_entry_outcomes_check(session)
        await sp.commit()
    except Exception:
        await sp.rollback()
        _logger.exception("missing-outcomes audit check failed")

    sp = await session.begin_nested()
    try:
        result.missing_observations = await run_missing_observations_check(session)
        await sp.commit()
    except Exception:
        await sp.rollback()
        _logger.exception("missing-observations audit check failed")

    return result


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _range_key(
    row: RowMapping,
) -> tuple[str | None, str | None, int | None, int | None]:
    return (
        str(row["log_source_id"]) if row["log_source_id"] else None,
        str(row["id"]) if row.get("id") else None,
        row.get("start_index"),
        row.get("end_index"),
    )


def _range_key_from_outcomes_row(
    row: RowMapping,
) -> tuple[str | None, str | None, int | None, int | None]:
    return (
        str(row["log_source_id"]) if row["log_source_id"] else None,
        str(row["range_id"]) if row.get("range_id") else None,
        row.get("start_index"),
        row.get("end_index"),
    )


def _obs_key(
    row: RowMapping,
) -> tuple[str | None, str | None, int | None, int | None]:
    idx = row.get("log_index")
    return (
        str(row["log_source_id"]) if row["log_source_id"] else None,
        None,
        idx,
        idx,
    )


def _dt_str(dt: object) -> str | None:
    """Convert a datetime or None to an ISO 8601 string."""
    if dt is None:
        return None
    return str(dt)
