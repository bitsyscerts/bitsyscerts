"""Tests for certsapi.settings.router (GET/PUT /v1/settings/storage)."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from certsapi.app import create_app
from certsapi.config import Settings

_SETTINGS = Settings.model_validate(
    {"database_url": "postgresql+psycopg://localhost/test"}
)
_NOW = datetime(2026, 5, 7, 12, 0, 0, tzinfo=UTC)


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
    row.updated_at = overrides.get("updated_at", _NOW)
    row.updated_by = overrides.get("updated_by", None)
    return row


@pytest.mark.asyncio
async def test_get_storage_settings_bootstraps_lite_when_not_seeded() -> None:
    """GET /v1/settings/storage seeds the default Lite profile when empty."""
    app = create_app(_SETTINGS)
    row = _make_settings_row(updated_by="bootstrap")
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        with (
            patch(
                "certsapi.settings.repository.SettingsRepository.get_active_settings",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch(
                "certsapi.settings.service.bootstrap_settings_from_env",
                new_callable=AsyncMock,
                return_value=row,
            ),
        ):
            response = await client.get("/v1/settings/storage")

    assert response.status_code == 200
    body = response.json()
    assert body["storage_profile"] == "lite"
    assert body["updated_by"] == "bootstrap"


@pytest.mark.asyncio
async def test_get_storage_settings_returns_200_when_seeded() -> None:
    """GET /v1/settings/storage returns 200 with settings data."""
    row = _make_settings_row()
    app = create_app(_SETTINGS)
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        with patch(
            "certsapi.settings.repository.SettingsRepository.get_active_settings",
            new_callable=AsyncMock,
            return_value=row,
        ):
            response = await client.get("/v1/settings/storage")

    assert response.status_code == 200
    body = response.json()
    assert body["storage_profile"] == "lite"
    assert body["source"] == "database"


@pytest.mark.asyncio
async def test_put_storage_settings_returns_200() -> None:
    """PUT /v1/settings/storage returns 200 with result."""
    row = _make_settings_row()
    app = create_app(_SETTINGS)
    payload = {
        "storage_profile": "standard",
        "cert_storage_mode": "metadata_spki",
        "hostname_retention_mode": "forever",
        "backfill_days": 90,
        "cert_retention_days": 90,
        "observation_retention_days": 90,
        "entry_outcome_retention_days": 90,
        "metrics_retention_days": 30,
    }
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        with (
            patch(
                "certsapi.settings.repository.SettingsRepository.save_settings",
                new_callable=AsyncMock,
                return_value=row,
            ),
            patch(
                "certsapi.settings.service.record_profile_from_dict",
                new_callable=AsyncMock,
            ),
        ):
            response = await client.put("/v1/settings/storage", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "updated"
    assert body["storage_profile"] == "standard"


@pytest.mark.asyncio
async def test_put_archive_without_optin_returns_422() -> None:
    """PUT /v1/settings/storage with archive profile without optin returns 422."""
    app = create_app(_SETTINGS)
    payload = {
        "storage_profile": "archive",
        "cert_storage_mode": "full_der",
        "hostname_retention_mode": "forever",
        "backfill_days": 0,
        "cert_retention_days": 0,
        "observation_retention_days": 0,
        "entry_outcome_retention_days": 0,
        "metrics_retention_days": 90,
        "archive_explicit_optin": False,
    }
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.put("/v1/settings/storage", json=payload)

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_get_storage_settings_history_returns_200() -> None:
    """GET /v1/settings/storage/history returns 200 with list."""
    app = create_app(_SETTINGS)
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        with patch(
            "certsapi.settings.repository.SettingsRepository.get_settings_history",
            new_callable=AsyncMock,
            return_value=[],
        ):
            response = await client.get("/v1/settings/storage/history")

    assert response.status_code == 200
    assert response.json() == []
