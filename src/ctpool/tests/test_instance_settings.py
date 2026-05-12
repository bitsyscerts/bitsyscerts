"""Unit tests for ctpool.instance_settings.

Uses async mocks so no real DB connection is required.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ctpool.bootstrap_config import BootstrapConfig
from ctpool.instance_settings import (
    _validate_payload,
    bootstrap_settings_from_env,
    get_active_settings,
    update_settings,
)
from ctpool.models.instance_settings import CtInstanceSettings


def _make_session() -> MagicMock:
    session = MagicMock()
    session.execute = AsyncMock()
    return session


def _make_valid_payload(**overrides: object) -> dict:
    base: dict = {
        "storage_profile": "lite",
        "cert_storage_mode": "none",
        "hostname_retention_mode": "forever",
        "backfill_days": 30,
        "cert_retention_days": 1,
        "observation_retention_days": 7,
        "entry_outcome_retention_days": 7,
        "metrics_retention_days": 14,
    }
    base.update(overrides)
    return base


@pytest.mark.asyncio
async def test_get_active_settings_returns_none_when_empty() -> None:
    """get_active_settings returns None when the table is empty."""
    session = _make_session()
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = None
    session.execute.return_value = result_mock

    result = await get_active_settings(session)
    assert result is None


@pytest.mark.asyncio
async def test_get_active_settings_returns_row() -> None:
    """get_active_settings returns the ORM row when one exists."""
    row = MagicMock(spec=CtInstanceSettings)
    session = _make_session()
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = row
    session.execute.return_value = result_mock

    result = await get_active_settings(session)
    assert result is row


@pytest.mark.asyncio
async def test_bootstrap_skips_when_row_exists() -> None:
    """bootstrap_settings_from_env returns existing row without inserting."""
    existing = MagicMock(spec=CtInstanceSettings)
    session = _make_session()
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = existing
    session.execute.return_value = result_mock

    config = BootstrapConfig(profile="lite")
    returned = await bootstrap_settings_from_env(session, config)

    assert returned is existing
    session.add.assert_not_called()


@pytest.mark.asyncio
async def test_bootstrap_seeds_when_table_empty() -> None:
    """bootstrap_settings_from_env inserts a row when no row exists."""
    call_count = 0

    async def fake_execute(*_a: object, **_kw: object) -> MagicMock:
        nonlocal call_count
        call_count += 1
        mock = MagicMock()
        # First call: get_active_settings (returns None)
        # Subsequent calls: record_profile_from_dict internals
        mock.scalar_one_or_none.return_value = None
        return mock

    session = _make_session()
    session.execute.side_effect = fake_execute

    config = BootstrapConfig(profile="lite")

    with patch(
        "ctpool.instance_settings.record_profile_from_dict", new_callable=AsyncMock
    ):
        row = await bootstrap_settings_from_env(session, config)

    session.add.assert_called_once()
    assert row.storage_profile == "lite"


def test_validate_payload_accepts_valid() -> None:
    """_validate_payload does not raise for valid profile and mode."""
    _validate_payload(_make_valid_payload())  # should not raise


def test_validate_payload_rejects_invalid_profile() -> None:
    """_validate_payload raises ValueError for unknown profile."""
    with pytest.raises(ValueError, match="Invalid storage_profile"):
        _validate_payload(_make_valid_payload(storage_profile="turbo"))


def test_validate_payload_rejects_invalid_mode() -> None:
    """_validate_payload raises ValueError for unknown cert_storage_mode."""
    with pytest.raises(ValueError, match="Invalid cert_storage_mode"):
        _validate_payload(_make_valid_payload(cert_storage_mode="ultra_compressed"))


@pytest.mark.asyncio
async def test_update_settings_raises_on_invalid_profile() -> None:
    """update_settings propagates ValueError for invalid profile."""
    session = _make_session()
    with pytest.raises(ValueError, match="Invalid storage_profile"):
        await update_settings(
            session,
            _make_valid_payload(storage_profile="bad"),
        )


@pytest.mark.asyncio
async def test_update_settings_creates_row() -> None:
    """update_settings creates and adds a new settings row."""
    session = _make_session()

    with patch(
        "ctpool.instance_settings.record_profile_from_dict", new_callable=AsyncMock
    ):
        row = await update_settings(
            session,
            _make_valid_payload(),
            updated_by="api-user",
        )

    session.add.assert_called_once_with(row)
    assert row.storage_profile == "lite"
    assert row.updated_by == "api-user"
