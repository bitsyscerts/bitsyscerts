"""Tests for ctpool.database_init orchestration."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.exc import SQLAlchemyError

from ctpool.config import Settings
from ctpool.database_init import classify_target_database_state, run_init_db
from ctpool.exceptions import DatabaseInitError, DatabasePrivilegeError


def _settings(**overrides: object) -> Settings:
    base = {"database_url": "postgresql+psycopg://ctpool:ctpool@localhost:5432/ctpool"}
    base.update(overrides)
    return Settings.model_validate(base)


async def test_classify_target_database_state_reports_missing() -> None:
    with (
        patch(
            "ctpool.database_init.get_current_revision",
            new_callable=AsyncMock,
            side_effect=SQLAlchemyError("missing db"),
        ),
        patch("ctpool.database_init.database_exists_sync", return_value=False),
    ):
        state = await classify_target_database_state(_settings())

    assert state == "missing"


async def test_classify_target_database_state_reports_inconsistent() -> None:
    with (
        patch(
            "ctpool.database_init.get_current_revision",
            new_callable=AsyncMock,
            return_value="c5d4f0f9a123",
        ),
        patch(
            "ctpool.database_init.get_missing_core_tables",
            new_callable=AsyncMock,
            return_value=("hostnames",),
        ),
    ):
        state = await classify_target_database_state(_settings())

    assert state == "inconsistent"


async def test_classify_state_raises_when_target_db_is_unreachable() -> None:
    with (
        patch(
            "ctpool.database_init.get_current_revision",
            new_callable=AsyncMock,
            side_effect=SQLAlchemyError("bad credentials"),
        ),
        patch("ctpool.database_init.database_exists_sync", return_value=True),
    ):
        with pytest.raises(DatabaseInitError, match="Unable to connect"):
            await classify_target_database_state(_settings())


async def test_run_init_db_creates_missing_database_then_migrates() -> None:
    with (
        patch(
            "ctpool.database_init.classify_target_database_state",
            new_callable=AsyncMock,
            return_value="missing",
        ),
        patch(
            "ctpool.database_init.create_database_if_missing_sync",
            return_value=True,
        ),
        patch(
            "ctpool.database_init.run_upgrade_head",
            new_callable=AsyncMock,
        ) as mock_upgrade,
    ):
        action = await run_init_db(_settings())

    assert action == "created"
    mock_upgrade.assert_awaited_once()


async def test_run_init_db_migrates_ready_database_in_place() -> None:
    with (
        patch(
            "ctpool.database_init.classify_target_database_state",
            new_callable=AsyncMock,
            return_value="ready",
        ),
        patch(
            "ctpool.database_init.run_upgrade_head", new_callable=AsyncMock
        ) as mock_upgrade,
    ):
        action = await run_init_db(_settings())

    assert action == "migrated"
    mock_upgrade.assert_awaited_once()


async def test_run_init_db_refuses_inconsistent_database_without_force() -> None:
    with patch(
        "ctpool.database_init.classify_target_database_state",
        new_callable=AsyncMock,
        return_value="inconsistent",
    ):
        with pytest.raises(DatabaseInitError, match="init-db --force"):
            await run_init_db(_settings())


async def test_run_init_db_force_recreates_database_then_migrates() -> None:
    with (
        patch("ctpool.database_init.recreate_database_sync", return_value=True),
        patch(
            "ctpool.database_init.run_upgrade_head", new_callable=AsyncMock
        ) as mock_upgrade,
    ):
        action = await run_init_db(_settings(), force=True)

    assert action == "recreated"
    mock_upgrade.assert_awaited_once()


async def test_run_init_db_force_propagates_privilege_errors() -> None:
    with patch(
        "ctpool.database_init.recreate_database_sync",
        side_effect=DatabasePrivilegeError("no privilege"),
    ):
        with pytest.raises(DatabasePrivilegeError, match="no privilege"):
            await run_init_db(_settings(), force=True)
