"""Unit tests for ctpool.audit_constants — constant values and frozensets."""

from __future__ import annotations

from ctpool.audit_constants import (
    ALL_FINDING_TYPES,
    ALL_RANGE_KINDS,
    ALL_REPAIR_ACTIONS,
    ALL_SEVERITIES,
    ALL_STATUSES,
    DEFAULT_REPAIR_SEVERITIES,
    FINDING_TYPE_FAILED_BACKFILL_RANGE,
    FINDING_TYPE_MISSING_ENTRY_OUTCOMES,
    FINDING_TYPE_MISSING_OBSERVATIONS_WITHOUT_OUTCOME,
    FINDING_TYPE_STALE_BACKFILL_CLAIM,
    FINDING_TYPE_STATS_INCONSISTENCY,
    FINDING_TYPE_TAIL_CURSOR_GAP,
    RANGE_KIND_BACKFILL,
    RANGE_KIND_REPAIR,
    REPAIR_ACTION_FAILED_RANGE_REQUEUED,
    REPAIR_ACTION_NOT_SUPPORTED,
    REPAIR_ACTION_REPAIR_RANGE_CREATED,
    REPAIR_ACTION_STALE_CLAIM_REQUEUED,
    REPAIR_ACTION_STORED_OUTCOMES_BACKFILLED,
    SEVERITY_CRITICAL,
    SEVERITY_ERROR,
    SEVERITY_INFO,
    SEVERITY_WARNING,
    STATUS_FAILED,
    STATUS_IGNORED,
    STATUS_OPEN,
    STATUS_REPAIR_ATTEMPTED,
    STATUS_RESOLVED,
)


def test_all_finding_types_contains_expected_values() -> None:
    """ALL_FINDING_TYPES contains exactly the six expected type strings."""
    assert FINDING_TYPE_STALE_BACKFILL_CLAIM in ALL_FINDING_TYPES
    assert FINDING_TYPE_FAILED_BACKFILL_RANGE in ALL_FINDING_TYPES
    assert FINDING_TYPE_MISSING_ENTRY_OUTCOMES in ALL_FINDING_TYPES
    assert FINDING_TYPE_MISSING_OBSERVATIONS_WITHOUT_OUTCOME in ALL_FINDING_TYPES
    assert FINDING_TYPE_TAIL_CURSOR_GAP in ALL_FINDING_TYPES
    assert FINDING_TYPE_STATS_INCONSISTENCY in ALL_FINDING_TYPES
    assert len(ALL_FINDING_TYPES) == 6


def test_all_severities_contains_expected_values() -> None:
    """ALL_SEVERITIES contains exactly the four severity strings."""
    assert SEVERITY_CRITICAL in ALL_SEVERITIES
    assert SEVERITY_ERROR in ALL_SEVERITIES
    assert SEVERITY_WARNING in ALL_SEVERITIES
    assert SEVERITY_INFO in ALL_SEVERITIES
    assert len(ALL_SEVERITIES) == 4


def test_default_repair_severities_excludes_warning_and_info() -> None:
    """DEFAULT_REPAIR_SEVERITIES only includes critical and error by default."""
    assert SEVERITY_CRITICAL in DEFAULT_REPAIR_SEVERITIES
    assert SEVERITY_ERROR in DEFAULT_REPAIR_SEVERITIES
    assert SEVERITY_WARNING not in DEFAULT_REPAIR_SEVERITIES
    assert SEVERITY_INFO not in DEFAULT_REPAIR_SEVERITIES


def test_all_statuses_contains_expected_values() -> None:
    """ALL_STATUSES contains exactly five status strings."""
    assert STATUS_OPEN in ALL_STATUSES
    assert STATUS_REPAIR_ATTEMPTED in ALL_STATUSES
    assert STATUS_RESOLVED in ALL_STATUSES
    assert STATUS_IGNORED in ALL_STATUSES
    assert STATUS_FAILED in ALL_STATUSES
    assert len(ALL_STATUSES) == 5


def test_all_range_kinds_contains_expected_values() -> None:
    """ALL_RANGE_KINDS contains exactly two values."""
    assert RANGE_KIND_BACKFILL in ALL_RANGE_KINDS
    assert RANGE_KIND_REPAIR in ALL_RANGE_KINDS
    assert len(ALL_RANGE_KINDS) == 2


def test_all_repair_actions_contains_expected_values() -> None:
    """ALL_REPAIR_ACTIONS contains exactly five action strings."""
    assert REPAIR_ACTION_STALE_CLAIM_REQUEUED in ALL_REPAIR_ACTIONS
    assert REPAIR_ACTION_FAILED_RANGE_REQUEUED in ALL_REPAIR_ACTIONS
    assert REPAIR_ACTION_REPAIR_RANGE_CREATED in ALL_REPAIR_ACTIONS
    assert REPAIR_ACTION_STORED_OUTCOMES_BACKFILLED in ALL_REPAIR_ACTIONS
    assert REPAIR_ACTION_NOT_SUPPORTED in ALL_REPAIR_ACTIONS
    assert len(ALL_REPAIR_ACTIONS) == 5


def test_all_frozensets_are_immutable() -> None:
    """All exported constants are frozenset instances (immutable)."""
    assert isinstance(ALL_FINDING_TYPES, frozenset)
    assert isinstance(ALL_SEVERITIES, frozenset)
    assert isinstance(ALL_STATUSES, frozenset)
    assert isinstance(ALL_RANGE_KINDS, frozenset)
    assert isinstance(ALL_REPAIR_ACTIONS, frozenset)
    assert isinstance(DEFAULT_REPAIR_SEVERITIES, frozenset)
