"""Audit gap detection and repair string constants.

Parallel to ``outcome_constants`` — always use these symbols rather than bare
strings so that typos are caught at import time.

Exports:
    FINDING_TYPE_* — Allowed values for ct_audit_findings.finding_type.
    SEVERITY_*     — Allowed values for ct_audit_findings.severity.
    STATUS_*       — Allowed values for ct_audit_findings.status.
    RANGE_KIND_*   — Allowed values for ct_log_backfill_ranges.range_kind.
    REPAIR_ACTION_* — Allowed values for ct_audit_findings.repair_action.
    ALL_FINDING_TYPES, ALL_SEVERITIES, ALL_STATUSES, ALL_RANGE_KINDS, ALL_REPAIR_ACTIONS
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Finding types
# ---------------------------------------------------------------------------

FINDING_TYPE_STALE_BACKFILL_CLAIM: str = "stale_backfill_claim"
FINDING_TYPE_FAILED_BACKFILL_RANGE: str = "failed_backfill_range"
FINDING_TYPE_MISSING_ENTRY_OUTCOMES: str = "missing_entry_outcomes"
FINDING_TYPE_MISSING_OBSERVATIONS_WITHOUT_OUTCOME: str = (
    "missing_observations_without_outcome"
)
FINDING_TYPE_TAIL_CURSOR_GAP: str = "tail_cursor_gap"
FINDING_TYPE_STATS_INCONSISTENCY: str = "stats_inconsistency"

ALL_FINDING_TYPES: frozenset[str] = frozenset(
    [
        FINDING_TYPE_STALE_BACKFILL_CLAIM,
        FINDING_TYPE_FAILED_BACKFILL_RANGE,
        FINDING_TYPE_MISSING_ENTRY_OUTCOMES,
        FINDING_TYPE_MISSING_OBSERVATIONS_WITHOUT_OUTCOME,
        FINDING_TYPE_TAIL_CURSOR_GAP,
        FINDING_TYPE_STATS_INCONSISTENCY,
    ]
)

# ---------------------------------------------------------------------------
# Severities (ordered worst → best)
# ---------------------------------------------------------------------------

SEVERITY_CRITICAL: str = "critical"
SEVERITY_ERROR: str = "error"
SEVERITY_WARNING: str = "warning"
SEVERITY_INFO: str = "info"

ALL_SEVERITIES: frozenset[str] = frozenset(
    [SEVERITY_CRITICAL, SEVERITY_ERROR, SEVERITY_WARNING, SEVERITY_INFO]
)

# Severities that the repair command processes by default (critical + error)
DEFAULT_REPAIR_SEVERITIES: frozenset[str] = frozenset(
    [SEVERITY_CRITICAL, SEVERITY_ERROR]
)

# ---------------------------------------------------------------------------
# Finding statuses
# ---------------------------------------------------------------------------

STATUS_OPEN: str = "open"
STATUS_REPAIR_ATTEMPTED: str = "repair_attempted"
STATUS_RESOLVED: str = "resolved"
STATUS_IGNORED: str = "ignored"
STATUS_FAILED: str = "failed"

ALL_STATUSES: frozenset[str] = frozenset(
    [
        STATUS_OPEN,
        STATUS_REPAIR_ATTEMPTED,
        STATUS_RESOLVED,
        STATUS_IGNORED,
        STATUS_FAILED,
    ]
)

# ---------------------------------------------------------------------------
# Range kinds
# ---------------------------------------------------------------------------

RANGE_KIND_BACKFILL: str = "backfill"
RANGE_KIND_REPAIR: str = "repair"

ALL_RANGE_KINDS: frozenset[str] = frozenset([RANGE_KIND_BACKFILL, RANGE_KIND_REPAIR])

# ---------------------------------------------------------------------------
# Repair actions
# ---------------------------------------------------------------------------

REPAIR_ACTION_STALE_CLAIM_REQUEUED: str = "stale_claim_requeued"
REPAIR_ACTION_FAILED_RANGE_REQUEUED: str = "failed_range_requeued"
REPAIR_ACTION_REPAIR_RANGE_CREATED: str = "repair_range_created"
REPAIR_ACTION_STORED_OUTCOMES_BACKFILLED: str = "stored_outcomes_backfilled"
REPAIR_ACTION_NOT_SUPPORTED: str = "not_supported"

ALL_REPAIR_ACTIONS: frozenset[str] = frozenset(
    [
        REPAIR_ACTION_STALE_CLAIM_REQUEUED,
        REPAIR_ACTION_FAILED_RANGE_REQUEUED,
        REPAIR_ACTION_REPAIR_RANGE_CREATED,
        REPAIR_ACTION_STORED_OUTCOMES_BACKFILLED,
        REPAIR_ACTION_NOT_SUPPORTED,
    ]
)
