"""Unit tests for ctpool.audit_repair — pure logic and mock-based tests.

These tests run without a live database.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ctpool.audit_constants import (
    DEFAULT_REPAIR_SEVERITIES,
    FINDING_TYPE_FAILED_BACKFILL_RANGE,
    FINDING_TYPE_STALE_BACKFILL_CLAIM,
    REPAIR_ACTION_FAILED_RANGE_REQUEUED,
    REPAIR_ACTION_NOT_SUPPORTED,
    REPAIR_ACTION_STALE_CLAIM_REQUEUED,
    STATUS_IGNORED,
    STATUS_OPEN,
    STATUS_RESOLVED,
)
from ctpool.audit_repair import (
    RepairOptions,
    apply_repair,
    fetch_repairable_findings,
    mark_finding_ignored,
)
from ctpool.audit_repair_strategies import (
    repair_failed_backfill_range,
    repair_stale_backfill_claim,
    repair_unsupported,
)
from ctpool.models.audit_finding import CtAuditFinding


def _make_finding(
    finding_type: str = FINDING_TYPE_STALE_BACKFILL_CLAIM,
    severity: str = "warning",
    repair_attempt_count: int = 0,
) -> CtAuditFinding:
    f = CtAuditFinding(
        finding_type=finding_type,
        severity=severity,
        status=STATUS_OPEN,
    )
    f.id = uuid.uuid4()
    f.repair_attempt_count = repair_attempt_count
    return f


# ---------------------------------------------------------------------------
# RepairOptions
# ---------------------------------------------------------------------------


def test_repair_options_default_severities() -> None:
    """Default RepairOptions uses DEFAULT_REPAIR_SEVERITIES."""
    opts = RepairOptions()
    assert opts.severities == DEFAULT_REPAIR_SEVERITIES


def test_repair_options_default_dry_run_is_true() -> None:
    """Default dry_run is True."""
    opts = RepairOptions()
    assert opts.dry_run is True


def test_repair_options_default_limit() -> None:
    """Default limit is 100."""
    opts = RepairOptions()
    assert opts.limit == 100


# ---------------------------------------------------------------------------
# fetch_repairable_findings — invalid type
# ---------------------------------------------------------------------------


async def test_fetch_repairable_findings_raises_for_unknown_type() -> None:
    """fetch_repairable_findings raises ValueError for unknown finding type."""
    session = AsyncMock()
    options = RepairOptions(finding_type="not_a_valid_type", dry_run=True)
    with pytest.raises(ValueError, match="Unknown finding type"):
        await fetch_repairable_findings(session, options)


# ---------------------------------------------------------------------------
# apply_repair — counter increment and dry_run
# ---------------------------------------------------------------------------


async def test_apply_repair_increments_attempt_count_unit() -> None:
    """apply_repair increments repair_attempt_count before calling strategy."""
    finding = _make_finding(repair_attempt_count=0)
    mock_strategy = AsyncMock(return_value=finding)
    session = AsyncMock()

    with patch(
        "ctpool.audit_repair._STRATEGY_MAP",
        {FINDING_TYPE_STALE_BACKFILL_CLAIM: mock_strategy},
    ):
        await apply_repair(finding, session)

    assert finding.repair_attempt_count == 1
    mock_strategy.assert_awaited_once_with(finding, session)


async def test_apply_repair_always_flushes_never_rolls_back() -> None:
    """apply_repair always flushes; dry_run is managed by the caller via savepoints."""
    finding = _make_finding(repair_attempt_count=0)
    mock_strategy = AsyncMock(return_value=finding)
    session = AsyncMock()

    with patch(
        "ctpool.audit_repair._STRATEGY_MAP",
        {FINDING_TYPE_STALE_BACKFILL_CLAIM: mock_strategy},
    ):
        await apply_repair(finding, session)

    session.flush.assert_awaited_once()
    session.rollback.assert_not_called()


async def test_apply_repair_calls_flush() -> None:
    """apply_repair calls session.flush() to surface violations inside the savepoint."""
    finding = _make_finding(repair_attempt_count=0)
    mock_strategy = AsyncMock(return_value=finding)
    session = AsyncMock()

    with patch(
        "ctpool.audit_repair._STRATEGY_MAP",
        {FINDING_TYPE_STALE_BACKFILL_CLAIM: mock_strategy},
    ):
        await apply_repair(finding, session)

    session.flush.assert_awaited_once()


async def test_apply_repair_uses_unsupported_strategy_for_unknown_type() -> None:
    """apply_repair falls back to repair_unsupported for unknown finding type."""
    finding = _make_finding(finding_type="completely_unknown")
    session = AsyncMock()
    mock_unsupported = AsyncMock(return_value=finding)

    with patch("ctpool.audit_repair.repair_unsupported", mock_unsupported):
        await apply_repair(finding, session)

    mock_unsupported.assert_awaited_once_with(finding, session)


# ---------------------------------------------------------------------------
# mark_finding_ignored — not-found case
# ---------------------------------------------------------------------------


async def test_mark_finding_ignored_returns_none_when_not_found_unit() -> None:
    """mark_finding_ignored returns None when scalar_one_or_none returns None."""
    session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    session.execute = AsyncMock(return_value=mock_result)

    result = await mark_finding_ignored(session, uuid.uuid4(), reason="not found test")
    assert result is None


async def test_mark_finding_ignored_sets_status_unit() -> None:
    """mark_finding_ignored sets status=ignored and stores reason (unit test)."""
    finding = _make_finding()
    session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = finding
    session.execute = AsyncMock(return_value=mock_result)

    result = await mark_finding_ignored(session, finding.id, reason="unit test reason")
    assert result is not None
    assert result.status == STATUS_IGNORED
    assert result.repair_details_json == {"reason": "unit test reason"}
    assert result.resolved_by == "operator"


# ---------------------------------------------------------------------------
# repair_unsupported — no DB required (only sets attributes)
# ---------------------------------------------------------------------------


async def test_repair_unsupported_sets_failed_status() -> None:
    """repair_unsupported marks finding as failed with not_supported action."""
    finding = _make_finding(finding_type="unknown_type")
    session = AsyncMock()
    result = await repair_unsupported(finding, session)
    assert result.status == "failed"
    assert result.repair_action == REPAIR_ACTION_NOT_SUPPORTED
    assert result.repair_details_json is not None
    assert "unknown_type" in result.repair_details_json.get("reason", "")


async def test_repair_unsupported_sets_attempted_at() -> None:
    """repair_unsupported sets repair_attempted_at to a non-None datetime."""
    finding = _make_finding(finding_type="unsupported_xyz")
    session = AsyncMock()
    result = await repair_unsupported(finding, session)
    assert result.repair_attempted_at is not None


# ---------------------------------------------------------------------------
# fetch_repairable_findings — with valid options (covers lines 72, 79-84)
# ---------------------------------------------------------------------------


async def test_fetch_repairable_findings_with_finding_id_unit() -> None:
    """fetch_repairable_findings applies finding_id filter (unit test)."""
    finding = _make_finding()
    session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value = [finding]
    session.execute = AsyncMock(return_value=mock_result)

    fid = uuid.uuid4()
    options = RepairOptions(finding_id=fid, dry_run=True)
    results = await fetch_repairable_findings(session, options)
    assert results == [finding]
    session.execute.assert_awaited_once()


async def test_fetch_repairable_findings_with_valid_type_unit() -> None:
    """fetch_repairable_findings filters by finding_type when valid (unit test)."""
    finding = _make_finding()
    session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value = [finding]
    session.execute = AsyncMock(return_value=mock_result)

    options = RepairOptions(
        finding_type=FINDING_TYPE_STALE_BACKFILL_CLAIM, dry_run=True
    )
    results = await fetch_repairable_findings(session, options)
    assert results == [finding]
    session.execute.assert_awaited_once()


# ---------------------------------------------------------------------------
# repair_stale_backfill_claim — unit tests with mocked session
# ---------------------------------------------------------------------------


async def test_repair_stale_backfill_claim_resolves_finding_unit() -> None:
    """repair_stale_backfill_claim marks finding resolved when update succeeds."""
    finding = _make_finding(finding_type=FINDING_TYPE_STALE_BACKFILL_CLAIM)
    finding.range_id = __import__("uuid").uuid4()
    session = AsyncMock()
    mock_result = MagicMock()
    mock_result.rowcount = 1
    session.execute = AsyncMock(return_value=mock_result)

    updated = await repair_stale_backfill_claim(finding, session)

    assert updated.status == STATUS_RESOLVED
    assert updated.repair_action == REPAIR_ACTION_STALE_CLAIM_REQUEUED
    assert updated.resolved_by == "fix-audit-findings"


async def test_repair_stale_claim_rowcount_zero_concurrent_unit() -> None:
    """repair_stale_backfill_claim notes concurrent resolution when rowcount==0."""
    finding = _make_finding(finding_type=FINDING_TYPE_STALE_BACKFILL_CLAIM)
    finding.range_id = __import__("uuid").uuid4()
    session = AsyncMock()
    mock_result = MagicMock()
    mock_result.rowcount = 0
    session.execute = AsyncMock(return_value=mock_result)

    updated = await repair_stale_backfill_claim(finding, session)

    assert updated.status == STATUS_RESOLVED  # still resolved
    assert updated.repair_details_json == {"concurrent_resolution": True}


# ---------------------------------------------------------------------------
# repair_failed_backfill_range — unit tests with mocked session
# ---------------------------------------------------------------------------


async def test_repair_failed_backfill_range_resolves_finding_unit() -> None:
    """repair_failed_backfill_range marks finding resolved when update succeeds."""
    finding = _make_finding(finding_type=FINDING_TYPE_FAILED_BACKFILL_RANGE)
    finding.range_id = __import__("uuid").uuid4()
    session = AsyncMock()
    mock_result = MagicMock()
    mock_result.rowcount = 1
    session.execute = AsyncMock(return_value=mock_result)

    updated = await repair_failed_backfill_range(finding, session)

    assert updated.status == STATUS_RESOLVED
    assert updated.repair_action == REPAIR_ACTION_FAILED_RANGE_REQUEUED
    assert updated.resolved_by == "fix-audit-findings"


async def test_repair_failed_range_rowcount_zero_concurrent_unit() -> None:
    """repair_failed_backfill_range notes concurrent resolution when rowcount==0."""
    finding = _make_finding(finding_type=FINDING_TYPE_FAILED_BACKFILL_RANGE)
    finding.range_id = __import__("uuid").uuid4()
    session = AsyncMock()
    mock_result = MagicMock()
    mock_result.rowcount = 0
    session.execute = AsyncMock(return_value=mock_result)

    updated = await repair_failed_backfill_range(finding, session)

    assert updated.status == STATUS_RESOLVED  # still resolved
    assert updated.repair_details_json == {"concurrent_resolution": True}
