"""Integration tests for ctpool.audit_repair and audit_repair_strategies.

Uses the real ctpool_test database; every test rolls back automatically.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ctpool.audit_constants import (
    FINDING_TYPE_FAILED_BACKFILL_RANGE,
    FINDING_TYPE_MISSING_ENTRY_OUTCOMES,
    FINDING_TYPE_MISSING_OBSERVATIONS_WITHOUT_OUTCOME,
    FINDING_TYPE_STALE_BACKFILL_CLAIM,
    FINDING_TYPE_STATS_INCONSISTENCY,
    RANGE_KIND_REPAIR,
    REPAIR_ACTION_FAILED_RANGE_REQUEUED,
    REPAIR_ACTION_NOT_SUPPORTED,
    REPAIR_ACTION_REPAIR_RANGE_CREATED,
    REPAIR_ACTION_STALE_CLAIM_REQUEUED,
    REPAIR_ACTION_STORED_OUTCOMES_BACKFILLED,
    STATUS_FAILED,
    STATUS_IGNORED,
    STATUS_OPEN,
    STATUS_REPAIR_ATTEMPTED,
    STATUS_RESOLVED,
)
from ctpool.audit_repair import (
    RepairOptions,
    apply_repair,
    fetch_repairable_findings,
    mark_finding_ignored,
)
from ctpool.models.audit_finding import CtAuditFinding
from ctpool.models.entry_outcome import CtEntryOutcome
from ctpool.models.log_backfill_range import CtLogBackfillRange
from ctpool.models.log_source import CtLogSource

pytestmark = pytest.mark.integration

_NOW = datetime.now(UTC)


def _make_source(url: str = "https://repair.example.com/") -> CtLogSource:
    return CtLogSource(
        id=uuid.uuid4(),
        log_id_b64="dGVzdA==",
        operator_name="Test Operator",
        description="Test CT Log",
        url=url,
        public_key_b64="a2V5==",
        log_state="usable",
        is_eligible_for_tail=True,
        is_eligible_for_backfill=True,
        source_list="chrome",
        first_seen_at=_NOW,
        last_synced_at=_NOW,
    )


def _make_range(
    source_id: uuid.UUID,
    *,
    start: int = 0,
    end: int = 4,
    status: str = "in_progress",
) -> CtLogBackfillRange:
    return CtLogBackfillRange(
        id=uuid.uuid4(),
        log_source_id=source_id,
        start_index=start,
        end_index=end,
        next_index=start,
        status=status,
    )


def _make_finding(
    *,
    finding_type: str = FINDING_TYPE_STALE_BACKFILL_CLAIM,
    severity: str = "warning",
    log_source_id: uuid.UUID | None = None,
    range_id: uuid.UUID | None = None,
    start_index: int | None = 0,
    end_index: int | None = 4,
) -> CtAuditFinding:
    return CtAuditFinding(
        finding_type=finding_type,
        severity=severity,
        status=STATUS_OPEN,
        log_source_id=log_source_id,
        range_id=range_id,
        start_index=start_index,
        end_index=end_index,
    )


# ---------------------------------------------------------------------------
# repair_stale_backfill_claim
# ---------------------------------------------------------------------------


async def test_repair_stale_backfill_claim_resets_range_to_pending(
    db_session: AsyncSession,
) -> None:
    """Stale claim repair resets range status to pending and resolves finding."""
    source = _make_source(url="https://repair-stale1.example.com/")
    db_session.add(source)
    await db_session.flush()
    rng = _make_range(source.id, status="in_progress")
    db_session.add(rng)
    await db_session.flush()
    finding = _make_finding(
        finding_type=FINDING_TYPE_STALE_BACKFILL_CLAIM,
        log_source_id=source.id,
        range_id=rng.id,
    )
    db_session.add(finding)
    await db_session.flush()

    updated = await apply_repair(finding, db_session)

    assert updated.status == STATUS_RESOLVED
    assert updated.repair_action == REPAIR_ACTION_STALE_CLAIM_REQUEUED
    assert updated.resolved_at is not None

    await db_session.refresh(rng)
    assert rng.status == "pending"
    assert rng.claimed_by is None


async def test_repair_stale_backfill_claim_clears_claim_metadata(
    db_session: AsyncSession,
) -> None:
    """Stale claim repair clears claimed_at and heartbeat_at from the range."""
    source = _make_source(url="https://repair-stale2.example.com/")
    db_session.add(source)
    await db_session.flush()
    rng = _make_range(source.id, status="in_progress")
    rng.claimed_by = "worker-old"
    rng.claimed_at = _NOW - timedelta(hours=2)
    rng.heartbeat_at = _NOW - timedelta(hours=2)
    db_session.add(rng)
    await db_session.flush()
    finding = _make_finding(
        finding_type=FINDING_TYPE_STALE_BACKFILL_CLAIM,
        log_source_id=source.id,
        range_id=rng.id,
    )
    db_session.add(finding)
    await db_session.flush()

    await apply_repair(finding, db_session)
    await db_session.refresh(rng)

    assert rng.claimed_by is None
    assert rng.claimed_at is None
    assert rng.heartbeat_at is None


# ---------------------------------------------------------------------------
# repair_failed_backfill_range
# ---------------------------------------------------------------------------


async def test_repair_failed_backfill_range_resets_to_pending(
    db_session: AsyncSession,
) -> None:
    """Failed range repair resets range to pending and resolves the finding."""
    source = _make_source(url="https://repair-failed1.example.com/")
    db_session.add(source)
    await db_session.flush()
    rng = _make_range(source.id, status="failed")
    db_session.add(rng)
    await db_session.flush()
    finding = _make_finding(
        finding_type=FINDING_TYPE_FAILED_BACKFILL_RANGE,
        severity="error",
        log_source_id=source.id,
        range_id=rng.id,
    )
    db_session.add(finding)
    await db_session.flush()

    updated = await apply_repair(finding, db_session)

    assert updated.status == STATUS_RESOLVED
    assert updated.repair_action == REPAIR_ACTION_FAILED_RANGE_REQUEUED

    await db_session.refresh(rng)
    assert rng.status == "pending"


# ---------------------------------------------------------------------------
# repair_missing_entry_outcomes
# ---------------------------------------------------------------------------


async def test_repair_missing_entry_outcomes_creates_repair_range(
    db_session: AsyncSession,
) -> None:
    """Missing outcomes repair creates a repair-kind range and marks attempted."""
    source = _make_source(url="https://repair-gap1.example.com/")
    db_session.add(source)
    await db_session.flush()
    finding = _make_finding(
        finding_type=FINDING_TYPE_MISSING_ENTRY_OUTCOMES,
        severity="error",
        log_source_id=source.id,
        start_index=10,
        end_index=20,
    )
    db_session.add(finding)
    await db_session.flush()

    updated = await apply_repair(finding, db_session)

    assert updated.status == STATUS_REPAIR_ATTEMPTED
    assert updated.repair_action == REPAIR_ACTION_REPAIR_RANGE_CREATED
    assert updated.range_id is not None

    repair_range = await db_session.get(CtLogBackfillRange, updated.range_id)
    assert repair_range is not None
    assert repair_range.range_kind == RANGE_KIND_REPAIR
    assert repair_range.start_index == 10
    assert repair_range.end_index == 20


# ---------------------------------------------------------------------------
# repair_missing_observations_without_outcome
# ---------------------------------------------------------------------------


async def test_repair_missing_observations_inserts_outcome_row(
    db_session: AsyncSession,
) -> None:
    """Orphan observation repair inserts a stored outcome and resolves finding."""
    source = _make_source(url="https://repair-obs1.example.com/")
    db_session.add(source)
    await db_session.flush()
    finding = _make_finding(
        finding_type=FINDING_TYPE_MISSING_OBSERVATIONS_WITHOUT_OUTCOME,
        severity="warning",
        log_source_id=source.id,
        start_index=55,
        end_index=55,
    )
    db_session.add(finding)
    await db_session.flush()

    updated = await apply_repair(finding, db_session)

    assert updated.status == STATUS_RESOLVED
    assert updated.repair_action == REPAIR_ACTION_STORED_OUTCOMES_BACKFILLED

    result = await db_session.execute(
        select(CtEntryOutcome).where(
            CtEntryOutcome.log_source_id == source.id,
            CtEntryOutcome.log_index == 55,
        )
    )
    assert result.scalar_one() is not None


async def test_repair_missing_observations_is_idempotent(
    db_session: AsyncSession,
) -> None:
    """Second repair call for the same observation does not raise an error."""
    source = _make_source(url="https://repair-obs2.example.com/")
    db_session.add(source)
    await db_session.flush()
    finding = _make_finding(
        finding_type=FINDING_TYPE_MISSING_OBSERVATIONS_WITHOUT_OUTCOME,
        severity="warning",
        log_source_id=source.id,
        start_index=66,
        end_index=66,
    )
    db_session.add(finding)
    await db_session.flush()

    await apply_repair(finding, db_session)
    finding.status = STATUS_OPEN
    updated = await apply_repair(finding, db_session)
    assert updated.status == STATUS_RESOLVED


# ---------------------------------------------------------------------------
# repair_unsupported
# ---------------------------------------------------------------------------


async def test_repair_unsupported_type_marks_failed(
    db_session: AsyncSession,
) -> None:
    """Unknown finding type results in status=failed with a reason."""
    finding = _make_finding(
        finding_type=FINDING_TYPE_STATS_INCONSISTENCY,
        severity="info",
    )
    db_session.add(finding)
    await db_session.flush()

    updated = await apply_repair(finding, db_session)

    assert updated.status == STATUS_FAILED
    assert updated.repair_action == REPAIR_ACTION_NOT_SUPPORTED
    assert updated.repair_details_json is not None
    assert "reason" in updated.repair_details_json


# ---------------------------------------------------------------------------
# dry_run
# ---------------------------------------------------------------------------


async def test_savepoint_rollback_does_not_persist_repair(
    db_session: AsyncSession,
) -> None:
    """Caller-managed savepoint rollback prevents repair from being persisted."""
    source = _make_source(url="https://repair-dry1.example.com/")
    db_session.add(source)
    await db_session.flush()
    rng = _make_range(source.id, status="failed")
    db_session.add(rng)
    await db_session.flush()
    finding = _make_finding(
        finding_type=FINDING_TYPE_FAILED_BACKFILL_RANGE,
        severity="error",
        log_source_id=source.id,
        range_id=rng.id,
    )
    db_session.add(finding)
    await db_session.flush()

    # Simulate the dry_run caller pattern: savepoint + rollback
    sp = await db_session.begin_nested()
    await apply_repair(finding, db_session)
    await sp.rollback()

    # Refresh from DB — range and finding should be in original state
    await db_session.refresh(rng)
    await db_session.refresh(finding)
    assert rng.status == "failed"  # repair was rolled back
    assert finding.status == STATUS_OPEN  # finding not resolved


# ---------------------------------------------------------------------------
# repair_attempt_count
# ---------------------------------------------------------------------------


async def test_apply_repair_increments_attempt_count(
    db_session: AsyncSession,
) -> None:
    """Each apply_repair call increments repair_attempt_count."""
    source = _make_source(url="https://repair-count1.example.com/")
    db_session.add(source)
    await db_session.flush()
    rng = _make_range(source.id, status="failed")
    db_session.add(rng)
    await db_session.flush()
    finding = _make_finding(
        finding_type=FINDING_TYPE_FAILED_BACKFILL_RANGE,
        severity="error",
        log_source_id=source.id,
        range_id=rng.id,
    )
    db_session.add(finding)
    await db_session.flush()

    await apply_repair(finding, db_session)
    assert finding.repair_attempt_count == 1


# ---------------------------------------------------------------------------
# fetch_repairable_findings
# ---------------------------------------------------------------------------


async def test_fetch_repairable_findings_filters_by_severity(
    db_session: AsyncSession,
) -> None:
    """fetch_repairable_findings respects the severities filter."""
    info_finding = _make_finding(
        finding_type=FINDING_TYPE_STALE_BACKFILL_CLAIM, severity="info"
    )
    db_session.add(info_finding)
    critical_finding = _make_finding(
        finding_type=FINDING_TYPE_STALE_BACKFILL_CLAIM, severity="critical"
    )
    db_session.add(critical_finding)
    await db_session.flush()

    options = RepairOptions(severities=frozenset(["critical"]), dry_run=True)
    results = await fetch_repairable_findings(db_session, options)
    result_ids = {str(f.id) for f in results}

    assert str(critical_finding.id) in result_ids
    assert str(info_finding.id) not in result_ids


async def test_fetch_repairable_findings_filters_by_type(
    db_session: AsyncSession,
) -> None:
    """fetch_repairable_findings respects the finding_type filter."""
    finding = _make_finding(
        finding_type=FINDING_TYPE_FAILED_BACKFILL_RANGE, severity="error"
    )
    db_session.add(finding)
    await db_session.flush()

    options = RepairOptions(
        finding_type=FINDING_TYPE_FAILED_BACKFILL_RANGE,
        severities=frozenset(["error"]),
        dry_run=True,
    )
    results = await fetch_repairable_findings(db_session, options)
    assert any(str(f.id) == str(finding.id) for f in results)


async def test_fetch_repairable_findings_invalid_type_raises(
    db_session: AsyncSession,
) -> None:
    """fetch_repairable_findings raises ValueError for an unknown finding type."""
    options = RepairOptions(finding_type="not_a_real_type", dry_run=True)
    with pytest.raises(ValueError, match="Unknown finding type"):
        await fetch_repairable_findings(db_session, options)


# ---------------------------------------------------------------------------
# mark_finding_ignored
# ---------------------------------------------------------------------------


async def test_mark_finding_ignored_sets_status(
    db_session: AsyncSession,
) -> None:
    """mark_finding_ignored sets the finding status to ignored."""
    finding = _make_finding(finding_type=FINDING_TYPE_STALE_BACKFILL_CLAIM)
    db_session.add(finding)
    await db_session.flush()

    updated = await mark_finding_ignored(db_session, finding.id, reason="test reason")
    assert updated is not None
    assert updated.status == STATUS_IGNORED
    assert updated.repair_details_json == {"reason": "test reason"}


async def test_mark_finding_ignored_returns_none_for_unknown_id(
    db_session: AsyncSession,
) -> None:
    """mark_finding_ignored returns None when the finding UUID does not exist."""
    result = await mark_finding_ignored(
        db_session, uuid.uuid4(), reason="no such finding"
    )
    assert result is None
