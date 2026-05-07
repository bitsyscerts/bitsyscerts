"""Dispatches open audit findings to their repair strategy.

Exports:
    RepairOptions      — Dataclass capturing all CLI filter/limit flags.
    apply_repair       — Apply the correct strategy to a single finding.
    fetch_repairable_findings — Query open findings matching filter options.
    mark_finding_ignored      — Mark a single finding as ignored.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ctpool.audit_constants import (
    ALL_FINDING_TYPES,
    DEFAULT_REPAIR_SEVERITIES,
    FINDING_TYPE_FAILED_BACKFILL_RANGE,
    FINDING_TYPE_MISSING_ENTRY_OUTCOMES,
    FINDING_TYPE_MISSING_OBSERVATIONS_WITHOUT_OUTCOME,
    FINDING_TYPE_STALE_BACKFILL_CLAIM,
    STATUS_IGNORED,
    STATUS_OPEN,
    STATUS_REPAIR_ATTEMPTED,
)
from ctpool.audit_repair_strategies import (
    repair_failed_backfill_range,
    repair_missing_entry_outcomes,
    repair_missing_observations_without_outcome,
    repair_stale_backfill_claim,
    repair_unsupported,
)
from ctpool.models.audit_finding import CtAuditFinding

_STRATEGY_MAP = {
    FINDING_TYPE_STALE_BACKFILL_CLAIM: repair_stale_backfill_claim,
    FINDING_TYPE_FAILED_BACKFILL_RANGE: repair_failed_backfill_range,
    FINDING_TYPE_MISSING_ENTRY_OUTCOMES: repair_missing_entry_outcomes,
    FINDING_TYPE_MISSING_OBSERVATIONS_WITHOUT_OUTCOME: (
        repair_missing_observations_without_outcome
    ),
}

# Findings that are safe to re-attempt after a previous attempt
_REPAIRABLE_STATUSES = frozenset([STATUS_OPEN, STATUS_REPAIR_ATTEMPTED])


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
    """Query open (or repair_attempted) findings matching the given options."""
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
