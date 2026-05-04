"""Tests for HealthService — DB probe and error suppression."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from certsapi.health.service import HealthService


class TestHealthService:
    async def test_reachable_db_returns_ok(self) -> None:
        session = AsyncMock()
        session.execute.return_value = MagicMock()
        service = HealthService(session)

        result = await service.check()

        assert result.status == "ok"
        assert result.db == "ok"

    async def test_unreachable_db_returns_error_without_raising(self) -> None:
        session = AsyncMock()
        session.execute.side_effect = Exception("connection refused")
        service = HealthService(session)

        result = await service.check()

        assert result.status == "ok"
        assert result.db == "error"

    async def test_any_exception_type_is_caught(self) -> None:
        session = AsyncMock()
        session.execute.side_effect = RuntimeError("boom")
        service = HealthService(session)

        result = await service.check()

        assert result.db == "error"
