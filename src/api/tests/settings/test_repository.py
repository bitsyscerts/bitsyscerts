"""Unit tests for certsapi.settings.repository."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from ctpool.models.instance_settings import CtInstanceSettings
from ctpool.models.storage_profile_history import CtStorageProfileHistory

from certsapi.settings.repository import SettingsRepository


def _make_session() -> MagicMock:
    session = MagicMock()
    session.execute = AsyncMock()
    session.flush = AsyncMock()
    return session


@pytest.mark.asyncio
async def test_get_active_settings_returns_none_when_empty() -> None:
    """get_active_settings returns None when no row exists."""
    session = _make_session()
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = None
    session.execute.return_value = result_mock

    repo = SettingsRepository(session)
    result = await repo.get_active_settings()

    assert result is None


@pytest.mark.asyncio
async def test_get_active_settings_returns_row() -> None:
    """get_active_settings returns the ORM row when present."""
    row = MagicMock(spec=CtInstanceSettings)
    session = _make_session()
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = row
    session.execute.return_value = result_mock

    repo = SettingsRepository(session)
    result = await repo.get_active_settings()

    assert result is row


@pytest.mark.asyncio
async def test_save_settings_adds_and_flushes() -> None:
    """save_settings adds the row and flushes the session."""
    session = _make_session()
    row = MagicMock(spec=CtInstanceSettings)

    repo = SettingsRepository(session)
    returned = await repo.save_settings(row)

    session.add.assert_called_once_with(row)
    session.flush.assert_awaited_once()
    assert returned is row


@pytest.mark.asyncio
async def test_get_settings_history_default_limit() -> None:
    """get_settings_history uses default limit 50."""
    history_row = MagicMock(spec=CtStorageProfileHistory)
    session = _make_session()
    scalars_mock = MagicMock()
    scalars_mock.all.return_value = [history_row]
    result_mock = MagicMock()
    result_mock.scalars.return_value = scalars_mock
    session.execute.return_value = result_mock

    repo = SettingsRepository(session)
    history = await repo.get_settings_history()

    assert len(history) == 1
    assert history[0] is history_row


@pytest.mark.asyncio
async def test_get_settings_history_custom_limit() -> None:
    """get_settings_history passes custom limit to the query."""
    session = _make_session()
    scalars_mock = MagicMock()
    scalars_mock.all.return_value = []
    result_mock = MagicMock()
    result_mock.scalars.return_value = scalars_mock
    session.execute.return_value = result_mock

    repo = SettingsRepository(session)
    history = await repo.get_settings_history(limit=10)

    assert isinstance(history, list)
