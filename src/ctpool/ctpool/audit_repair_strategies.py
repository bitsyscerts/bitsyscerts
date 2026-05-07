"""Conservative per-finding-type repair strategy functions.

Each strategy function accepts an open CtAuditFinding and an AsyncSession.
On success it returns an updated CtAuditFinding (not yet flushed) with the
repair_action and status set appropriately.

Dry-run guard is applied by the caller (audit_repair), not here.

Exports:
    repair_stale_backfill_claim
    repair_failed_backfill_range
    repair_missing_entry_outcomes
    repair_missing_observations_without_outcome
    repair_unsupported
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from ctpool.audit_constants import (
    FINDING_TYPE_MISSING_OBSERVATIONS_WITHOUT_OUTCOME,
    RANGE_KIND_REPAIR,
    REPAIR_ACTION_FAILED_RANGE_REQUEUED,
    REPAIR_ACTION_NOT_SUPPORTED,
    REPAIR_ACTION_REPAIR_RANGE_CREATED,
    REPAIR_ACTION_STALE_CLAIM_REQUEUED,
    REPAIR_ACTION_STORED_OUTCOMES_BACKFILLED,
    STATUS_FAILED,
    STATUS_REPAIR_ATTEMPTED,
    STATUS_RESOLVED,
)
from ctpool.models.audit_finding import CtAuditFinding
from ctpool.models.entry_outcome import CtEntryOutcome
from ctpool.models.log_backfill_range import CtLogBackfillRange
from ctpool.outcome_constants import OUTCOME_STORED


async def repair_stale_backfill_claim(
    finding: CtAuditFinding,
    session: AsyncSession,
) -> CtAuditFinding:
    """Reset a stale in_progress range back to pending.

    Preserves next_index so partial progress is retained.
    Sets finding status to resolved.
    """
    now = datetime.now(UTC)
    if finding.range_id is not None:
        result = await session.execute(
            update(CtLogBackfillRange)
            .where(CtLogBackfillRange.id == finding.range_id)
            .where(CtLogBackfillRange.status == "in_progress")
            .values(
                status="pending",
                claimed_by=None,
                claimed_at=None,
                heartbeat_at=None,
                updated_at=now,
            )
        )
        if result.rowcount == 0:
            # Range status already changed (e.g. worker completed it concurrently).
            # The stale condition is gone regardless — finding is still resolved.
            finding.repair_details_json = {"concurrent_resolution": True}
    finding.status = STATUS_RESOLVED
    finding.repair_action = REPAIR_ACTION_STALE_CLAIM_REQUEUED
    finding.repair_attempted_at = now
    finding.resolved_at = now
    finding.resolved_by = "fix-audit-findings"
    return finding


async def repair_failed_backfill_range(
    finding: CtAuditFinding,
    session: AsyncSession,
) -> CtAuditFinding:
    """Reset a failed backfill range back to pending so it can be retried.

    Clears claim metadata.  Sets finding status to resolved.
    """
    now = datetime.now(UTC)
    if finding.range_id is not None:
        result = await session.execute(
            update(CtLogBackfillRange)
            .where(CtLogBackfillRange.id == finding.range_id)
            .where(CtLogBackfillRange.status == "failed")
            .values(
                status="pending",
                claimed_by=None,
                claimed_at=None,
                heartbeat_at=None,
                updated_at=now,
            )
        )
        if result.rowcount == 0:
            # Range status already changed (e.g. worker retried it concurrently).
            # The failed condition is gone regardless — finding is still resolved.
            finding.repair_details_json = {"concurrent_resolution": True}
    finding.status = STATUS_RESOLVED
    finding.repair_action = REPAIR_ACTION_FAILED_RANGE_REQUEUED
    finding.repair_attempted_at = now
    finding.resolved_at = now
    finding.resolved_by = "fix-audit-findings"
    return finding


async def repair_missing_entry_outcomes(
    finding: CtAuditFinding,
    session: AsyncSession,
) -> CtAuditFinding:
    """Create a targeted repair backfill range covering the gap.

    Uses ON CONFLICT DO NOTHING to be idempotent — if a repair range already
    exists for this finding the INSERT is silently skipped.
    Sets finding status to repair_attempted.
    """
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    now = datetime.now(UTC)
    if finding.start_index is not None and finding.end_index is not None:
        stmt = (
            pg_insert(CtLogBackfillRange)
            .values(
                id=uuid.uuid4(),
                log_source_id=finding.log_source_id,
                start_index=finding.start_index,
                end_index=finding.end_index,
                next_index=finding.start_index,
                status="pending",
                range_kind=RANGE_KIND_REPAIR,
                repair_for_finding_id=finding.id,
            )
            .on_conflict_do_nothing(
                index_elements=["log_source_id", "start_index", "end_index"]
            )
            .returning(CtLogBackfillRange.id)
        )
        result = await session.execute(stmt)
        row = result.first()
        if row is not None:
            finding.range_id = row[0]
    finding.status = STATUS_REPAIR_ATTEMPTED
    finding.repair_action = REPAIR_ACTION_REPAIR_RANGE_CREATED
    finding.repair_attempted_at = now
    return finding


async def repair_missing_observations_without_outcome(
    finding: CtAuditFinding,
    session: AsyncSession,
) -> CtAuditFinding:
    """Insert a stored outcome for the orphaned observation.

    Uses ON CONFLICT DO NOTHING so the insert is idempotent.
    Sets finding status to resolved.
    """
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    now = datetime.now(UTC)
    if finding.log_source_id is not None and finding.start_index is not None:
        stmt = (
            pg_insert(CtEntryOutcome)
            .values(
                id=uuid.uuid4(),
                log_source_id=finding.log_source_id,
                log_index=finding.start_index,
                outcome=OUTCOME_STORED,
                first_seen_at=now,
            )
            .on_conflict_do_nothing(index_elements=["log_source_id", "log_index"])
        )
        await session.execute(stmt)
    finding.status = STATUS_RESOLVED
    finding.repair_action = REPAIR_ACTION_STORED_OUTCOMES_BACKFILLED
    finding.repair_attempted_at = now
    finding.resolved_at = now
    finding.resolved_by = "fix-audit-findings"
    return finding


async def repair_unsupported(
    finding: CtAuditFinding,
    _session: AsyncSession,
) -> CtAuditFinding:
    """Mark finding as failed because automatic repair is not supported."""
    finding.status = STATUS_FAILED
    finding.repair_action = REPAIR_ACTION_NOT_SUPPORTED
    finding.repair_attempted_at = datetime.now(UTC)
    finding.repair_details_json = {
        "reason": (
            f"Automatic repair not implemented for finding type: {finding.finding_type}"
        )
    }
    return finding


# Findings that produce an orphaned-observation are handled per-row, not per
# span, so the type constant is re-exported for the dispatcher.
FINDING_TYPE_OBS = FINDING_TYPE_MISSING_OBSERVATIONS_WITHOUT_OUTCOME
