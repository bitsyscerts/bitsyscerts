"""Unit tests for ctpool.prune_queries and ctpool.prune_safety.

Uses AsyncMock sessions; no database required.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from ctpool.prune_queries import (
    count_blocked_latest,
    count_blocked_missing_summary,
    count_prunable_certificates,
    find_prunable_certificate_ids,
)
from ctpool.prune_safety import DeletionCounts, delete_certificates_batch

_CUTOFF = datetime(2025, 1, 1, tzinfo=UTC)


def _scalar_result(value) -> MagicMock:
    r = MagicMock()
    r.scalar_one = MagicMock(return_value=value)
    return r


def _scalars_result(values: list) -> MagicMock:
    r = MagicMock()
    scalars = MagicMock()
    scalars.all = MagicMock(return_value=values)
    r.scalars = MagicMock(return_value=scalars)
    return r


def _rowcount_result(n: int) -> MagicMock:
    r = MagicMock()
    r.rowcount = n
    return r


# ---------------------------------------------------------------------------
# count_prunable_certificates
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_count_prunable_certificates_returns_zero():
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_scalar_result(0))
    result = await count_prunable_certificates(session, _CUTOFF)
    assert result == 0


@pytest.mark.asyncio
async def test_count_prunable_certificates_returns_count():
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_scalar_result(42))
    result = await count_prunable_certificates(session, _CUTOFF)
    assert result == 42


# ---------------------------------------------------------------------------
# find_prunable_certificate_ids
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_find_prunable_certificate_ids_empty():
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_scalars_result([]))
    result = await find_prunable_certificate_ids(session, _CUTOFF, batch_size=100)
    assert result == []


@pytest.mark.asyncio
async def test_find_prunable_certificate_ids_returns_uuids():
    ids = [uuid.uuid4(), uuid.uuid4()]
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_scalars_result([str(i) for i in ids]))
    result = await find_prunable_certificate_ids(session, _CUTOFF, batch_size=100)
    assert result == ids


# ---------------------------------------------------------------------------
# count_blocked_latest
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_count_blocked_latest_zero():
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_scalar_result(0))
    result = await count_blocked_latest(session, _CUTOFF)
    assert result == 0


@pytest.mark.asyncio
async def test_count_blocked_latest_some():
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_scalar_result(7))
    result = await count_blocked_latest(session, _CUTOFF)
    assert result == 7


# ---------------------------------------------------------------------------
# count_blocked_missing_summary
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_count_blocked_missing_summary_zero():
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_scalar_result(0))
    result = await count_blocked_missing_summary(session)
    assert result == 0


@pytest.mark.asyncio
async def test_count_blocked_missing_summary_some():
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_scalar_result(3))
    result = await count_blocked_missing_summary(session)
    assert result == 3


# ---------------------------------------------------------------------------
# delete_certificates_batch
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_certificates_batch_empty_list():
    session = AsyncMock()
    result = await delete_certificates_batch(session, [])
    assert result == DeletionCounts(0, 0, 0)
    session.execute.assert_not_called()


@pytest.mark.asyncio
async def test_delete_certificates_batch_returns_counts():
    session = AsyncMock()
    session.execute = AsyncMock(
        side_effect=[
            _rowcount_result(3),  # certificate_hostnames
            _rowcount_result(5),  # ct_log_observations
            _rowcount_result(2),  # certificates
        ]
    )
    ids = [uuid.uuid4(), uuid.uuid4()]
    result = await delete_certificates_batch(session, ids)

    assert result.deleted_certificates == 2
    assert result.deleted_certificate_hostnames == 3
    assert result.deleted_ct_observations == 5


@pytest.mark.asyncio
async def test_delete_certificates_batch_calls_three_deletes():
    session = AsyncMock()
    session.execute = AsyncMock(
        side_effect=[
            _rowcount_result(0),
            _rowcount_result(0),
            _rowcount_result(1),
        ]
    )
    await delete_certificates_batch(session, [uuid.uuid4()])
    assert session.execute.await_count == 3
