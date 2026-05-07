"""Unit tests for ctpool.audit_checker — pure functions and mock-based tests.

These tests run without a live database using unittest.mock.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ctpool.audit_checker import (
    AuditCheckResult,
    _dt_str,
    _existing_open_keys,
    _obs_key,
    _range_key,
    _range_key_from_outcomes_row,
    run_all_checks,
    run_failed_backfill_range_check,
    run_missing_entry_outcomes_check,
    run_missing_observations_check,
    run_stale_backfill_claim_check,
)
from ctpool.audit_constants import (
    FINDING_TYPE_FAILED_BACKFILL_RANGE,
    FINDING_TYPE_MISSING_ENTRY_OUTCOMES,
    FINDING_TYPE_MISSING_OBSERVATIONS_WITHOUT_OUTCOME,
    FINDING_TYPE_STALE_BACKFILL_CLAIM,
    SEVERITY_ERROR,
    SEVERITY_WARNING,
    STATUS_OPEN,
)
from ctpool.models.audit_finding import CtAuditFinding

# ---------------------------------------------------------------------------
# AuditCheckResult
# ---------------------------------------------------------------------------


def test_audit_check_result_total_new_findings_sums_all() -> None:
    """total_new_findings sums all four finding type counts."""
    result = AuditCheckResult(
        stale_claims=1,
        failed_ranges=2,
        missing_outcomes=3,
        missing_observations=4,
    )
    assert result.total_new_findings == 10


def test_audit_check_result_total_is_zero_when_empty() -> None:
    """total_new_findings is 0 when no findings were created."""
    result = AuditCheckResult()
    assert result.total_new_findings == 0


# ---------------------------------------------------------------------------
# Pure helper functions
# ---------------------------------------------------------------------------


def test_range_key_extracts_fields() -> None:
    """_range_key extracts log_source_id, id, start_index, end_index."""
    src_id = uuid.uuid4()
    rng_id = uuid.uuid4()
    row = MagicMock()
    row.__getitem__ = lambda self, k: {
        "log_source_id": src_id,
        "id": rng_id,
        "start_index": 10,
        "end_index": 20,
    }[k]
    row.get = lambda k, d=None: {
        "start_index": 10,
        "end_index": 20,
        "id": rng_id,
    }.get(k, d)

    key = _range_key(row)
    assert key == (str(src_id), str(rng_id), 10, 20)


def test_range_key_handles_none_source_id() -> None:
    """_range_key returns None for log_source_id when it is None."""
    row = MagicMock()
    row.__getitem__ = lambda self, k: {
        "log_source_id": None,
        "id": None,
        "start_index": 0,
        "end_index": 10,
    }[k]
    row.get = lambda k, d=None: {
        "start_index": 0,
        "end_index": 10,
        "id": None,
    }.get(k, d)

    key = _range_key(row)
    assert key[0] is None
    assert key[1] is None


def test_range_key_from_outcomes_row_uses_range_id() -> None:
    """_range_key_from_outcomes_row uses range_id not id."""
    src_id = uuid.uuid4()
    range_id = uuid.uuid4()
    row = MagicMock()
    row.__getitem__ = lambda self, k: {
        "log_source_id": src_id,
        "start_index": 5,
        "end_index": 9,
        "range_id": range_id,
    }[k]
    row.get = lambda k, d=None: {
        "range_id": range_id,
        "start_index": 5,
        "end_index": 9,
    }.get(k, d)

    key = _range_key_from_outcomes_row(row)
    assert key[1] == str(range_id)


def test_obs_key_sets_both_indices_from_log_index() -> None:
    """_obs_key sets both start and end index from log_index."""
    src_id = uuid.uuid4()
    row = MagicMock()
    row.__getitem__ = lambda self, k: {"log_source_id": src_id}[k]
    row.get = lambda k, d=None: {"log_index": 42}.get(k, d)

    key = _obs_key(row)
    assert key[2] == 42
    assert key[3] == 42


def test_dt_str_returns_none_for_none() -> None:
    """_dt_str returns None when passed None."""
    assert _dt_str(None) is None


def test_dt_str_returns_string_for_value() -> None:
    """_dt_str converts a non-None value to string."""
    result = _dt_str("2024-01-01T00:00:00")
    assert isinstance(result, str)
    assert result == "2024-01-01T00:00:00"


# ---------------------------------------------------------------------------
# run_stale_backfill_claim_check with mocked session/queries
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_session() -> AsyncMock:
    """A mock AsyncSession that tracks added objects."""
    session = AsyncMock()
    session.added_objects: list = []

    def _add(obj: object) -> None:
        session.added_objects.append(obj)

    session.add = MagicMock(side_effect=_add)
    return session


def _make_stale_row(
    src_id: uuid.UUID | None = None,
    rng_id: uuid.UUID | None = None,
) -> MagicMock:
    src_id = src_id or uuid.uuid4()
    rng_id = rng_id or uuid.uuid4()
    row = MagicMock()
    row.__getitem__ = lambda self, k: {
        "log_source_id": src_id,
        "id": rng_id,
        "start_index": 0,
        "end_index": 99,
        "claimed_by": "worker-1",
    }[k]
    row.get = lambda k, d=None: {
        "start_index": 0,
        "end_index": 99,
        "id": rng_id,
        "heartbeat_at": None,
        "claimed_by": "worker-1",
    }.get(k, d)
    return row


async def test_run_stale_backfill_claim_check_creates_finding_unit(
    mock_session: AsyncMock,
) -> None:
    """Stale rows are mapped to CtAuditFinding objects (unit test)."""
    row = _make_stale_row()

    with (
        patch(
            "ctpool.audit_checker.query_stale_backfill_claims",
            new=AsyncMock(return_value=[row]),
        ),
        patch(
            "ctpool.audit_checker._existing_open_keys",
            new=AsyncMock(return_value=set()),
        ),
    ):
        count = await run_stale_backfill_claim_check(mock_session, 3600)

    assert count == 1
    assert len(mock_session.added_objects) == 1
    finding = mock_session.added_objects[0]
    assert isinstance(finding, CtAuditFinding)
    assert finding.finding_type == FINDING_TYPE_STALE_BACKFILL_CLAIM
    assert finding.severity == SEVERITY_WARNING
    assert finding.status == STATUS_OPEN


async def test_run_stale_backfill_claim_check_dedup_unit(
    mock_session: AsyncMock,
) -> None:
    """A row already in existing_open_keys is skipped (unit test)."""
    src_id = uuid.uuid4()
    rng_id = uuid.uuid4()
    row = _make_stale_row(src_id=src_id, rng_id=rng_id)
    existing_key = (str(src_id), str(rng_id), 0, 99)

    with (
        patch(
            "ctpool.audit_checker.query_stale_backfill_claims",
            new=AsyncMock(return_value=[row]),
        ),
        patch(
            "ctpool.audit_checker._existing_open_keys",
            new=AsyncMock(return_value={existing_key}),
        ),
    ):
        count = await run_stale_backfill_claim_check(mock_session, 3600)

    assert count == 0
    assert len(mock_session.added_objects) == 0


async def test_run_failed_backfill_range_check_unit(
    mock_session: AsyncMock,
) -> None:
    """Failed range rows create error-severity findings (unit test)."""
    src_id = uuid.uuid4()
    rng_id = uuid.uuid4()
    row = MagicMock()
    row.__getitem__ = lambda self, k: {
        "log_source_id": src_id,
        "id": rng_id,
        "start_index": 0,
        "end_index": 4,
    }[k]
    row.get = lambda k, d=None: {
        "start_index": 0,
        "end_index": 4,
        "id": rng_id,
        "last_error": "timeout",
        "attempt_count": 3,
        "range_kind": "backfill",
    }.get(k, d)

    with (
        patch(
            "ctpool.audit_checker.query_failed_backfill_ranges",
            new=AsyncMock(return_value=[row]),
        ),
        patch(
            "ctpool.audit_checker._existing_open_keys",
            new=AsyncMock(return_value=set()),
        ),
    ):
        count = await run_failed_backfill_range_check(mock_session)

    assert count == 1
    finding = mock_session.added_objects[0]
    assert finding.severity == SEVERITY_ERROR
    assert finding.finding_type == FINDING_TYPE_FAILED_BACKFILL_RANGE


async def test_run_missing_entry_outcomes_check_unit(
    mock_session: AsyncMock,
) -> None:
    """Outcome gap rows create error findings with missing_count (unit test)."""
    src_id = uuid.uuid4()
    range_id = uuid.uuid4()
    row = MagicMock()
    row.__getitem__ = lambda self, k: {
        "log_source_id": src_id,
        "start_index": 0,
        "end_index": 9,
        "range_id": range_id,
        "missing_count": 5,
        "expected_count": 10,
        "actual_count": 5,
    }[k]
    row.get = lambda k, d=None: {
        "range_id": range_id,
        "start_index": 0,
        "end_index": 9,
        "missing_count": 5,
        "expected_count": 10,
        "actual_count": 5,
    }.get(k, d)

    with (
        patch(
            "ctpool.audit_checker.query_missing_entry_outcomes",
            new=AsyncMock(return_value=[row]),
        ),
        patch(
            "ctpool.audit_checker._existing_open_keys",
            new=AsyncMock(return_value=set()),
        ),
    ):
        count = await run_missing_entry_outcomes_check(mock_session)

    assert count == 1
    finding = mock_session.added_objects[0]
    assert finding.finding_type == FINDING_TYPE_MISSING_ENTRY_OUTCOMES
    assert finding.missing_count == 5


async def test_run_missing_observations_check_unit(
    mock_session: AsyncMock,
) -> None:
    """Observation gap rows create warning findings (unit test)."""
    src_id = uuid.uuid4()
    obs_id = uuid.uuid4()
    row = MagicMock()
    row.__getitem__ = lambda self, k: {
        "log_source_id": src_id,
        "log_index": 42,
        "observation_id": obs_id,
    }[k]
    row.get = lambda k, d=None: {
        "log_index": 42,
        "observation_id": obs_id,
    }.get(k, d)

    with (
        patch(
            "ctpool.audit_checker.query_missing_observations_without_outcome",
            new=AsyncMock(return_value=[row]),
        ),
        patch(
            "ctpool.audit_checker._existing_open_keys",
            new=AsyncMock(return_value=set()),
        ),
    ):
        count = await run_missing_observations_check(mock_session)

    assert count == 1
    finding = mock_session.added_objects[0]
    assert finding.finding_type == FINDING_TYPE_MISSING_OBSERVATIONS_WITHOUT_OUTCOME
    assert finding.severity == SEVERITY_WARNING
    assert finding.start_index == 42


async def test_run_all_checks_aggregates_unit(
    mock_session: AsyncMock,
) -> None:
    """run_all_checks aggregates results from all sub-checks (unit test)."""
    with (
        patch(
            "ctpool.audit_checker.run_stale_backfill_claim_check",
            new=AsyncMock(return_value=1),
        ),
        patch(
            "ctpool.audit_checker.run_failed_backfill_range_check",
            new=AsyncMock(return_value=2),
        ),
        patch(
            "ctpool.audit_checker.run_missing_entry_outcomes_check",
            new=AsyncMock(return_value=3),
        ),
        patch(
            "ctpool.audit_checker.run_missing_observations_check",
            new=AsyncMock(return_value=4),
        ),
    ):
        result = await run_all_checks(mock_session, claim_timeout_seconds=3600)

    assert result.stale_claims == 1
    assert result.failed_ranges == 2
    assert result.missing_outcomes == 3
    assert result.missing_observations == 4
    assert result.total_new_findings == 10


# ---------------------------------------------------------------------------
# _existing_open_keys — covers the function body (lines 67-78)
# ---------------------------------------------------------------------------


async def test_existing_open_keys_builds_set_from_session_rows() -> None:
    """_existing_open_keys returns a set of tuples built from session rows."""
    src_id = uuid.uuid4()
    rng_id = uuid.uuid4()
    mock_row = MagicMock()
    mock_row.log_source_id = src_id
    mock_row.range_id = rng_id
    mock_row.start_index = 5
    mock_row.end_index = 15

    mock_result = MagicMock()
    mock_result.__iter__ = MagicMock(return_value=iter([mock_row]))
    session = AsyncMock()
    session.execute = AsyncMock(return_value=mock_result)

    result = await _existing_open_keys(session, "stale_backfill_claim")
    assert result == {(str(src_id), str(rng_id), 5, 15)}


async def test_existing_open_keys_handles_none_ids() -> None:
    """_existing_open_keys returns None values when IDs are None."""
    mock_row = MagicMock()
    mock_row.log_source_id = None
    mock_row.range_id = None
    mock_row.start_index = 0
    mock_row.end_index = 4

    mock_result = MagicMock()
    mock_result.__iter__ = MagicMock(return_value=iter([mock_row]))
    session = AsyncMock()
    session.execute = AsyncMock(return_value=mock_result)

    result = await _existing_open_keys(session, "failed_backfill_range")
    assert result == {(None, None, 0, 4)}


# ---------------------------------------------------------------------------
# Dedup (continue) branches for run_failed / run_missing_* checks
# ---------------------------------------------------------------------------


async def test_run_failed_backfill_range_check_dedup_unit(
    mock_session: AsyncMock,
) -> None:
    """run_failed_backfill_range_check skips rows already in existing keys."""
    src_id = uuid.uuid4()
    rng_id = uuid.uuid4()
    row = MagicMock()
    row.__getitem__ = lambda self, k: {
        "log_source_id": src_id,
        "id": rng_id,
        "start_index": 0,
        "end_index": 4,
    }[k]
    row.get = lambda k, d=None: {
        "start_index": 0,
        "end_index": 4,
        "id": rng_id,
    }.get(k, d)
    existing_key = (str(src_id), str(rng_id), 0, 4)

    with (
        patch(
            "ctpool.audit_checker.query_failed_backfill_ranges",
            new=AsyncMock(return_value=[row]),
        ),
        patch(
            "ctpool.audit_checker._existing_open_keys",
            new=AsyncMock(return_value={existing_key}),
        ),
    ):
        count = await run_failed_backfill_range_check(mock_session)

    assert count == 0
    assert len(mock_session.added_objects) == 0


async def test_run_missing_entry_outcomes_check_dedup_unit(
    mock_session: AsyncMock,
) -> None:
    """run_missing_entry_outcomes_check skips already-known finding keys."""
    src_id = uuid.uuid4()
    range_id = uuid.uuid4()
    row = MagicMock()
    row.__getitem__ = lambda self, k: {
        "log_source_id": src_id,
        "start_index": 0,
        "end_index": 9,
        "range_id": range_id,
        "missing_count": 5,
        "expected_count": 10,
        "actual_count": 5,
    }[k]
    row.get = lambda k, d=None: {
        "range_id": range_id,
        "start_index": 0,
        "end_index": 9,
    }.get(k, d)
    existing_key = (str(src_id), str(range_id), 0, 9)

    with (
        patch(
            "ctpool.audit_checker.query_missing_entry_outcomes",
            new=AsyncMock(return_value=[row]),
        ),
        patch(
            "ctpool.audit_checker._existing_open_keys",
            new=AsyncMock(return_value={existing_key}),
        ),
    ):
        count = await run_missing_entry_outcomes_check(mock_session)

    assert count == 0
    assert len(mock_session.added_objects) == 0


async def test_run_missing_observations_check_dedup_unit(
    mock_session: AsyncMock,
) -> None:
    """run_missing_observations_check skips already-known observation keys."""
    src_id = uuid.uuid4()
    obs_id = uuid.uuid4()
    row = MagicMock()
    row.__getitem__ = lambda self, k: {
        "log_source_id": src_id,
        "log_index": 42,
        "observation_id": obs_id,
    }[k]
    row.get = lambda k, d=None: {
        "log_index": 42,
        "observation_id": obs_id,
    }.get(k, d)
    existing_key = (str(src_id), None, 42, 42)

    with (
        patch(
            "ctpool.audit_checker.query_missing_observations_without_outcome",
            new=AsyncMock(return_value=[row]),
        ),
        patch(
            "ctpool.audit_checker._existing_open_keys",
            new=AsyncMock(return_value={existing_key}),
        ),
    ):
        count = await run_missing_observations_check(mock_session)

    assert count == 0
    assert len(mock_session.added_objects) == 0


# ---------------------------------------------------------------------------
# run_all_checks — exception isolation (savepoint rollback paths)
# ---------------------------------------------------------------------------


async def test_run_all_checks_continues_when_one_check_raises_unit(
    mock_session: AsyncMock,
) -> None:
    """A failing check is isolated; remaining checks still run and are counted."""
    with (
        patch(
            "ctpool.audit_checker.run_stale_backfill_claim_check",
            new=AsyncMock(side_effect=RuntimeError("db error")),
        ),
        patch(
            "ctpool.audit_checker.run_failed_backfill_range_check",
            new=AsyncMock(return_value=2),
        ),
        patch(
            "ctpool.audit_checker.run_missing_entry_outcomes_check",
            new=AsyncMock(return_value=3),
        ),
        patch(
            "ctpool.audit_checker.run_missing_observations_check",
            new=AsyncMock(return_value=4),
        ),
    ):
        result = await run_all_checks(mock_session, claim_timeout_seconds=3600)

    assert result.stale_claims == 0  # failed check defaults to 0
    assert result.failed_ranges == 2
    assert result.missing_outcomes == 3
    assert result.missing_observations == 4


async def test_run_all_checks_all_checks_fail_returns_zeros_unit(
    mock_session: AsyncMock,
) -> None:
    """run_all_checks returns all-zero result when every check fails."""
    err = RuntimeError("forced failure")
    with (
        patch(
            "ctpool.audit_checker.run_stale_backfill_claim_check",
            new=AsyncMock(side_effect=err),
        ),
        patch(
            "ctpool.audit_checker.run_failed_backfill_range_check",
            new=AsyncMock(side_effect=err),
        ),
        patch(
            "ctpool.audit_checker.run_missing_entry_outcomes_check",
            new=AsyncMock(side_effect=err),
        ),
        patch(
            "ctpool.audit_checker.run_missing_observations_check",
            new=AsyncMock(side_effect=err),
        ),
    ):
        result = await run_all_checks(mock_session, claim_timeout_seconds=3600)

    assert result.total_new_findings == 0
