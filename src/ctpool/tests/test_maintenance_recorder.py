"""Tests for ctpool.maintenance_recorder.

The recorder is a thin wrapper around an async session factory; tests
mock the session's begin/add/execute lifecycle so behaviour can be
exercised without standing up a real database.
"""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from ctpool.maintenance_recorder import (
    finalize_maintenance_run,
    insert_maintenance_run,
)


def _build_factory(captured: dict[str, Any]) -> MagicMock:
    """Build a factory whose session records adds and update statements."""
    session = MagicMock()
    session.add = MagicMock(
        side_effect=lambda obj: captured.setdefault("added", []).append(obj)
    )
    session.execute = AsyncMock(
        side_effect=lambda stmt: captured.setdefault("executed", []).append(stmt)
    )

    @asynccontextmanager
    async def _begin() -> Any:
        yield None

    session.begin = _begin

    @asynccontextmanager
    async def _session_ctx() -> Any:
        yield session

    factory = MagicMock(side_effect=lambda: _session_ctx())
    return factory


class TestInsertMaintenanceRun:
    @pytest.mark.asyncio
    async def test_returns_uuid_and_records_running_row(self) -> None:
        captured: dict[str, Any] = {}
        factory = _build_factory(captured)
        run_id = await insert_maintenance_run(
            factory,
            run_type="prune_for_storage_profile",
            mode="dry_run",
            storage_profile="lite",
            settings_hash="h",
        )
        assert isinstance(run_id, uuid.UUID)
        added = captured["added"][0]
        assert added.status == "running"
        assert added.mode == "dry_run"
        assert added.storage_profile == "lite"


class TestFinalizeMaintenanceRun:
    @pytest.mark.asyncio
    async def test_emits_update_with_terminal_counts(self) -> None:
        captured: dict[str, Any] = {}
        factory = _build_factory(captured)
        await finalize_maintenance_run(
            factory,
            uuid.uuid4(),
            status="complete",
            deleted_certificates=10,
            deleted_observations=20,
            preserved_hostnames=5,
            duration_ms=42,
            details={"k": "v"},
        )
        # The session must have executed exactly one UPDATE.
        assert "executed" in captured
        assert len(captured["executed"]) == 1

    @pytest.mark.asyncio
    async def test_records_failure_metadata(self) -> None:
        captured: dict[str, Any] = {}
        factory = _build_factory(captured)
        await finalize_maintenance_run(
            factory,
            uuid.uuid4(),
            status="failed",
            error_message="boom",
        )
        assert len(captured["executed"]) == 1
