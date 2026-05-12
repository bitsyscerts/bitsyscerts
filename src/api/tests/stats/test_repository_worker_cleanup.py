"""Unit tests for automatic worker cleanup in StatsRepository."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from certsapi.stats.repository import StatsRepository


@pytest.mark.asyncio
async def test_worker_summary_reaps_stale_workers_before_querying() -> None:
    """Live stats cleanup runs before the worker summary query."""
    session = AsyncMock()
    repo = StatsRepository(session)
    expected = {
        "active_total": 0,
        "stale_total": 0,
        "tail_active": 0,
        "backfill_active": 0,
        "stats_active": 0,
        "maintenance_active": 0,
        "unknown_active": 0,
        "items": [],
    }

    with (
        patch(
            "certsapi.stats.repository.reap_stale_worker_rows",
            AsyncMock(return_value=["host:1234"]),
        ) as reap_mock,
        patch(
            "certsapi.stats.repository.query_worker_summary",
            AsyncMock(return_value=expected),
        ) as query_mock,
    ):
        result = await repo.worker_summary(stale_seconds=300)

    reap_mock.assert_awaited_once_with(session, stale_seconds=300)
    query_mock.assert_awaited_once_with(session, stale_seconds=300)
    assert result == expected
