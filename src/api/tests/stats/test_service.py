"""Tests for StatsService — mocked repository."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from certsapi.stats.models import StatsResponse
from certsapi.stats.service import StatsService


def _make_row(
    log_id: uuid.UUID | None = None,
    complete: int = 5,
    total: int = 10,
    tail_pos: int = 500,
) -> MagicMock:
    row = MagicMock()
    row.__getitem__.side_effect = lambda k: {
        "id": log_id or uuid.uuid4(),
        "description": "Test Log",
        "url": "https://ct.test/",
        "log_state": "usable",
        "tail_position": tail_pos,
        "last_tail_sync": datetime.now(UTC),
        "complete_ranges": complete,
        "total_ranges": total,
    }[k]
    return row


class TestStatsService:
    async def test_returns_stats_response(self) -> None:
        repo = AsyncMock()
        repo.total_hostnames.return_value = 100
        repo.total_certificates.return_value = 50
        repo.total_logs.return_value = 3
        repo.per_log_stats.return_value = [_make_row()]
        service = StatsService(repo)

        result = await service.get_stats()

        assert isinstance(result, StatsResponse)
        assert result.total_hostnames == 100
        assert result.total_certificates == 50
        assert result.total_logs == 3

    async def test_logs_list_populated(self) -> None:
        repo = AsyncMock()
        repo.total_hostnames.return_value = 0
        repo.total_certificates.return_value = 0
        repo.total_logs.return_value = 1
        repo.per_log_stats.return_value = [_make_row()]
        service = StatsService(repo)

        result = await service.get_stats()

        assert len(result.logs) == 1

    async def test_backfill_pct_computed_correctly(self) -> None:
        repo = AsyncMock()
        repo.total_hostnames.return_value = 0
        repo.total_certificates.return_value = 0
        repo.total_logs.return_value = 1
        repo.per_log_stats.return_value = [_make_row(complete=3, total=4)]
        service = StatsService(repo)

        result = await service.get_stats()

        assert result.logs[0].backfill_complete_pct == pytest.approx(75.0)

    async def test_backfill_pct_null_when_no_ranges(self) -> None:
        repo = AsyncMock()
        repo.total_hostnames.return_value = 0
        repo.total_certificates.return_value = 0
        repo.total_logs.return_value = 1
        repo.per_log_stats.return_value = [_make_row(complete=0, total=0)]
        service = StatsService(repo)

        result = await service.get_stats()

        assert result.logs[0].backfill_complete_pct is None

    async def test_empty_logs_when_no_log_sources(self) -> None:
        repo = AsyncMock()
        repo.total_hostnames.return_value = 0
        repo.total_certificates.return_value = 0
        repo.total_logs.return_value = 0
        repo.per_log_stats.return_value = []
        service = StatsService(repo)

        result = await service.get_stats()

        assert result.logs == []
