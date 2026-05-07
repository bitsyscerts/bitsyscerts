"""Unit tests for certsapi.settings.service."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from certsapi.settings.models import UpdateStorageSettingsRequest
from certsapi.settings.service import SettingsService


def _make_repo(row: object = None) -> AsyncMock:
    repo = AsyncMock()
    repo.get_active_settings.return_value = row
    repo.save_settings.side_effect = lambda r: r
    repo._session = AsyncMock()
    return repo


def _make_settings_row(**overrides: object) -> MagicMock:
    row = MagicMock()
    row.storage_profile = overrides.get("storage_profile", "lite")
    row.cert_storage_mode = overrides.get("cert_storage_mode", "none")
    row.hostname_retention_mode = overrides.get("hostname_retention_mode", "forever")
    row.backfill_days = overrides.get("backfill_days", 30)
    row.cert_retention_days = overrides.get("cert_retention_days", 1)
    row.observation_retention_days = overrides.get("observation_retention_days", 7)
    row.entry_outcome_retention_days = overrides.get("entry_outcome_retention_days", 7)
    row.metrics_retention_days = overrides.get("metrics_retention_days", 14)
    row.settings_hash = overrides.get("settings_hash", "abc123")
    row.updated_at = overrides.get("updated_at", datetime(2026, 5, 7, tzinfo=UTC))
    row.updated_by = overrides.get("updated_by", None)
    return row


@pytest.mark.asyncio
async def test_get_settings_returns_none_when_not_seeded() -> None:
    """get_settings returns None when no row exists."""
    repo = _make_repo(row=None)
    service = SettingsService(repo)
    result = await service.get_settings()
    assert result is None


@pytest.mark.asyncio
async def test_get_settings_returns_response_model() -> None:
    """get_settings converts the ORM row to StorageSettingsResponse."""
    row = _make_settings_row()
    repo = _make_repo(row=row)
    service = SettingsService(repo)
    result = await service.get_settings()
    assert result is not None
    assert result.storage_profile == "lite"
    assert result.source == "database"


@pytest.mark.asyncio
async def test_update_settings_creates_row() -> None:
    """update_settings persists a new row and returns a result."""
    repo = _make_repo()
    service = SettingsService(repo)
    request = UpdateStorageSettingsRequest(
        storage_profile="standard",
        cert_storage_mode="metadata_spki",
        hostname_retention_mode="forever",
        backfill_days=90,
        cert_retention_days=90,
        observation_retention_days=90,
        entry_outcome_retention_days=90,
        metrics_retention_days=30,
    )
    with patch(
        "certsapi.settings.service.record_profile_from_dict",
        new_callable=AsyncMock,
    ):
        result = await service.update_settings(request)

    repo.save_settings.assert_awaited_once()
    assert result.status == "updated"
    assert result.storage_profile == "standard"


@pytest.mark.asyncio
async def test_update_archive_without_optin_raises() -> None:
    """update_settings raises ValueError for archive without opt-in."""
    repo = _make_repo()
    service = SettingsService(repo)
    request = UpdateStorageSettingsRequest(
        storage_profile="archive",
        cert_storage_mode="full_der",
        hostname_retention_mode="forever",
        backfill_days=0,
        cert_retention_days=0,
        observation_retention_days=0,
        entry_outcome_retention_days=0,
        metrics_retention_days=90,
        archive_explicit_optin=False,
    )
    with pytest.raises(ValueError, match="archive_explicit_optin"):
        await service.update_settings(request)


@pytest.mark.asyncio
async def test_update_archive_with_optin_succeeds() -> None:
    """update_settings succeeds for archive with explicit opt-in."""
    repo = _make_repo()
    service = SettingsService(repo)
    request = UpdateStorageSettingsRequest(
        storage_profile="archive",
        cert_storage_mode="full_der",
        hostname_retention_mode="forever",
        backfill_days=0,
        cert_retention_days=0,
        observation_retention_days=0,
        entry_outcome_retention_days=0,
        metrics_retention_days=90,
        archive_explicit_optin=True,
    )
    with patch(
        "certsapi.settings.service.record_profile_from_dict",
        new_callable=AsyncMock,
    ):
        result = await service.update_settings(request)

    assert result.status == "updated"
    assert result.storage_profile == "archive"


@pytest.mark.asyncio
async def test_get_history_returns_list() -> None:
    """get_history returns a list of StorageSettingsHistoryItem."""
    history_row = MagicMock()
    history_row.settings_hash = "abc"
    history_row.storage_profile = "lite"
    history_row.cert_storage_mode = "none"
    history_row.hostname_retention_mode = "forever"
    history_row.backfill_days = 30
    history_row.cert_retention_days = 1
    history_row.observation_retention_days = 7
    history_row.entry_outcome_retention_days = 7
    history_row.metrics_retention_days = 14
    history_row.first_seen_at = datetime(2026, 5, 7, tzinfo=UTC)
    history_row.last_seen_at = datetime(2026, 5, 7, tzinfo=UTC)
    history_row.is_current = True

    repo = _make_repo()
    repo.get_settings_history.return_value = [history_row]
    service = SettingsService(repo)
    items = await service.get_history()

    assert len(items) == 1
    assert items[0].storage_profile == "lite"
    assert items[0].is_current is True
