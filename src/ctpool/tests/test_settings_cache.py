"""Unit tests for ctpool.settings_cache."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ctpool.settings_cache import SettingsCache


def _make_row(profile: str = "lite") -> MagicMock:
    row = MagicMock()
    row.storage_profile = profile
    return row


@pytest.mark.asyncio
async def test_initial_state_is_stale() -> None:
    """A newly created cache is stale and has no cached value."""
    cache = SettingsCache(refresh_seconds=60)
    assert cache.is_stale()
    assert cache.cached is None


@pytest.mark.asyncio
async def test_refresh_queries_db_when_stale() -> None:
    """refresh_if_stale issues a DB query on first call."""
    row = _make_row()
    with patch(
        "ctpool.settings_cache.get_active_settings",
        new_callable=AsyncMock,
        return_value=row,
    ):
        cache = SettingsCache(refresh_seconds=60)
        session = AsyncMock()
        result = await cache.refresh_if_stale(session)

    assert result is row
    assert cache.cached is row


@pytest.mark.asyncio
async def test_refresh_skips_db_when_fresh() -> None:
    """refresh_if_stale skips DB query when cache is still fresh."""
    row = _make_row()
    with patch(
        "ctpool.settings_cache.get_active_settings",
        new_callable=AsyncMock,
        return_value=row,
    ) as mock_get:
        cache = SettingsCache(refresh_seconds=60)
        session = AsyncMock()
        await cache.refresh_if_stale(session)
        await cache.refresh_if_stale(session)

    assert mock_get.call_count == 1


@pytest.mark.asyncio
async def test_refresh_queries_after_ttl_expires() -> None:
    """refresh_if_stale issues a new DB query after TTL expires."""
    row1 = _make_row("lite")
    row2 = _make_row("standard")
    call_count = 0

    async def fake_get(_session: object) -> MagicMock:
        nonlocal call_count
        call_count += 1
        return row1 if call_count == 1 else row2

    with patch("ctpool.settings_cache.get_active_settings", side_effect=fake_get):
        cache = SettingsCache(refresh_seconds=1)
        session = AsyncMock()
        await cache.refresh_if_stale(session)
        # Manually expire the cache
        cache._last_refreshed = datetime.now(UTC) - timedelta(seconds=2)
        result = await cache.refresh_if_stale(session)

    assert result is row2
    assert call_count == 2


@pytest.mark.asyncio
async def test_force_refresh_always_queries_db() -> None:
    """force_refresh always queries the DB regardless of TTL."""
    row1 = _make_row("lite")
    row2 = _make_row("standard")
    call_count = 0

    async def fake_get(_session: object) -> MagicMock:
        nonlocal call_count
        call_count += 1
        return row1 if call_count == 1 else row2

    with patch("ctpool.settings_cache.get_active_settings", side_effect=fake_get):
        cache = SettingsCache(refresh_seconds=3600)
        session = AsyncMock()
        await cache.refresh_if_stale(session)
        result = await cache.force_refresh(session)

    assert result is row2
    assert call_count == 2


@pytest.mark.asyncio
async def test_cache_is_not_stale_immediately_after_refresh() -> None:
    """After a refresh, is_stale() returns False."""
    with patch(
        "ctpool.settings_cache.get_active_settings",
        new_callable=AsyncMock,
        return_value=None,
    ):
        cache = SettingsCache(refresh_seconds=60)
        session = AsyncMock()
        await cache.refresh_if_stale(session)
        assert not cache.is_stale()
