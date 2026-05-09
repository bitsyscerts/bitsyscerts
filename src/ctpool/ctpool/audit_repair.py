"""Dispatches open audit findings to their repair strategy.

Exports:
    RepairOptions      — Dataclass capturing all CLI filter/limit flags.
    apply_repair       — Apply the correct strategy to a single finding.
    fetch_repairable_findings        — Query open findings matching filter options.
    mark_finding_ignored             — Mark a single finding as ignored.
    resolve_repair_finding           — Resolve a repair_attempted finding whose
                                       repair range has completed.
    resolve_orphaned_repair_findings — Bulk-resolve repair_attempted findings
                                       with no active repair range (backlog
                                       cleanup pre-pass).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy import exists, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ctpool.audit_constants import (
    ALL_FINDING_TYPES,
    DEFAULT_REPAIR_SEVERITIES,
    FINDING_TYPE_FAILED_BACKFILL_RANGE,
    FINDING_TYPE_MISSING_ENTRY_OUTCOMES,
    FINDING_TYPE_MISSING_OBSERVATIONS_WITHOUT_OUTCOME,
    FINDING_TYPE_STALE_BACKFILL_CLAIM,
    STATUS_FAILED,
    STATUS_IGNORED,
    STATUS_OPEN,
    STATUS_REPAIR_ATTEMPTED,
    STATUS_RESOLVED,
)
from ctpool.audit_repair_strategies import (
    repair_failed_backfill_range,
    repair_missing_entry_outcomes,
    repair_missing_observations_without_outcome,
    repair_stale_backfill_claim,
    repair_unsupported,
)
from ctpool.models.audit_finding import CtAuditFinding
from ctpool.models.log_backfill_range import CtLogBackfillRange

_ACTIVE_RANGE_STATUSES = frozenset(["pending", "in_progress"])

_STRATEGY_MAP = {
    FINDING_TYPE_STALE_BACKFILL_CLAIM: repair_stale_backfill_claim,
    FINDING_TYPE_FAILED_BACKFILL_RANGE: repair_failed_backfill_range,
    FINDING_TYPE_MISSING_ENTRY_OUTCOMES: repair_missing_entry_outcomes,
    FINDING_TYPE_MISSING_OBSERVATIONS_WITHOUT_OUTCOME: (
        repair_missing_observations_without_outcome
    ),
}

# Only open findings are queued for repair.  repair_attempted findings already
# have an active repair range being processed by the backfill worker — they
# must not be re-queued.  Use resolve_orphaned_repair_findings() to clean up
# any repair_attempted findings whose ranges have already completed.
_REPAIRABLE_STATUSES = frozenset([STATUS_OPEN])


@dataclass
class RepairOptions:
    """Filter / limit options for fix-audit-findings."""

    finding_id: uuid.UUID | None = None
    finding_type: str | None = None
    severities: frozenset[str] = field(
        default_factory=lambda: DEFAULT_REPAIR_SEVERITIES
    )
    limit: int = 100
    dry_run: bool = True


async def fetch_repairable_findings(
    session: AsyncSession,
    options: RepairOptions,
) -> list[CtAuditFinding]:
    """Query open findings matching the given options."""
    stmt = select(CtAuditFinding).where(CtAuditFinding.status.in_(_REPAIRABLE_STATUSES))
    if options.finding_id is not None:
        stmt = stmt.where(CtAuditFinding.id == options.finding_id)
    if options.finding_type is not None:
        if options.finding_type not in ALL_FINDING_TYPES:
            raise ValueError(
                f"Unknown finding type: {options.finding_type!r}. "
                f"Valid types: {sorted(ALL_FINDING_TYPES)}"
            )
        stmt = stmt.where(CtAuditFinding.finding_type == options.finding_type)
    stmt = stmt.where(CtAuditFinding.severity.in_(options.severities))
    stmt = stmt.order_by(CtAuditFinding.created_at.asc())
    stmt = stmt.limit(options.limit)
    result = await session.execute(stmt)
    return list(result.scalars())


async def apply_repair(
    finding: CtAuditFinding,
    session: AsyncSession,
) -> CtAuditFinding:
    """Dispatch a finding to its repair strategy.

    The caller is responsible for wrapping this call in a savepoint
    (``session.begin_nested()``) and deciding whether to commit or roll back.
    Flushing inside the savepoint surfaces constraint violations before the
    savepoint is committed, keeping each finding's repair fully isolated.

    Args:
        finding: The CtAuditFinding to repair (must be in session).
        session: Active async database session.

    Returns:
        The (possibly modified) finding with repair metadata set.
    """
    strategy = _STRATEGY_MAP.get(finding.finding_type, repair_unsupported)
    finding.repair_attempt_count = (finding.repair_attempt_count or 0) + 1
    updated = await strategy(finding, session)
    await session.flush()
    return updated


async def mark_finding_ignored(
    session: AsyncSession,
    finding_id: uuid.UUID,
    reason: str,
) -> CtAuditFinding | None:
    """Mark a specific finding as ignored with an optional reason.

    Returns:
        The updated finding, or None if not found.
    """
    result = await session.execute(
        select(CtAuditFinding).where(CtAuditFinding.id == finding_id)
    )
    finding = result.scalar_one_or_none()
    if finding is None:
        return None
    finding.status = STATUS_IGNORED
    finding.repair_action = "ignored"
    finding.repair_details_json = {"reason": reason}
    finding.repair_attempted_at = datetime.now(UTC)
    finding.resolved_at = datetime.now(UTC)
    finding.resolved_by = "operator"
    await session.flush()
    return finding


async def resolve_repair_finding(
    session: AsyncSession,
    finding_id: uuid.UUID,
) -> None:
    """Resolve a repair_attempted finding whose repair range has now completed.

    Called by the backfill worker when a RANGE_KIND_REPAIR range finishes
    successfully.  This closes the audit finding lifecycle — without this step,
    repair_attempted findings accumulate and are re-processed on every
    fix-audit-findings run.

    No-op if the finding is not found or is already in a terminal state
    (resolved, ignored, failed).  This ensures the call is safe to make
    unconditionally from the completion path.

    Args:
        session:    Active async database session with an open transaction.
        finding_id: PK of the CtAuditFinding to resolve.
    """
    result = await session.execute(
        select(CtAuditFinding).where(CtAuditFinding.id == finding_id)
    )
    finding = result.scalar_one_or_none()
    if finding is None:
        return
    if finding.status in (STATUS_RESOLVED, STATUS_IGNORED, STATUS_FAILED):
        return
    now = datetime.now(UTC)
    finding.status = STATUS_RESOLVED
    finding.resolved_at = now
    finding.resolved_by = "backfill-worker"
    await session.flush()


async def resolve_orphaned_repair_findings(session: AsyncSession) -> int:
    """Resolve all repair_attempted findings that have no active repair range.

    A finding is considered orphaned when it is in the repair_attempted state
    but every repair range that was created for it has already completed or
    failed (i.e. no range with status 'pending' or 'in_progress' points to it).

    This is the backlog-cleanup pre-pass run at the start of fix-audit-findings.
    It handles findings that were stuck before resolve_repair_finding was wired
    into the backfill worker completion path.

    Args:
        session: Active async database session with an open transaction.

    Returns:
        Number of findings resolved.
    """
    now = datetime.now(UTC)
    active_range = (
        select(CtLogBackfillRange.id)
        .where(
            CtLogBackfillRange.repair_for_finding_id == CtAuditFinding.id,
            CtLogBackfillRange.status.in_(_ACTIVE_RANGE_STATUSES),
        )
        .correlate(CtAuditFinding)
    )
    stmt = (
        update(CtAuditFinding)
        .where(
            CtAuditFinding.status == STATUS_REPAIR_ATTEMPTED,
            ~exists(active_range),
        )
        .values(
            status=STATUS_RESOLVED,
            resolved_at=now,
            resolved_by="fix-audit-findings-cleanup",
        )
        .execution_options(synchronize_session=False)
    )
    result = await session.execute(stmt)
    return result.rowcount
