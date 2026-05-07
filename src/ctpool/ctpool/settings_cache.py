"""TTL cache wrapping active instance settings reads for ctpool workers.

Workers poll this cache on a configured refresh interval rather than
querying the database on every batch. This reduces DB load while
allowing runtime settings changes to propagate within one refresh cycle.

Exports:
    SettingsCache — Async TTL cache around get_active_settings.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

from ctpool.bootstrap_config import get_worker_refresh_config
from ctpool.instance_settings import get_active_settings
from ctpool.models.instance_settings import CtInstanceSettings


class SettingsCache:
    """Async TTL cache wrapping active instance settings reads.

    Call ``refresh_if_stale(session)`` at the top of each ingestion cycle
    and then read ``cached`` for the current settings snapshot.
    """

    def __init__(self, refresh_seconds: int | None = None) -> None:
        if refresh_seconds is None:
            refresh_seconds = get_worker_refresh_config().settings_refresh_seconds
        self._refresh_seconds = refresh_seconds
        self._cached: CtInstanceSettings | None = None
        self._last_refreshed: datetime | None = None
        self._lock = asyncio.Lock()

    @property
    def cached(self) -> CtInstanceSettings | None:
        """Return the last-cached settings row without a DB query."""
        return self._cached

    def is_stale(self) -> bool:
        """Return True if the cache needs a refresh."""
        if self._last_refreshed is None:
            return True
        elapsed = (datetime.now(UTC) - self._last_refreshed).total_seconds()
        return elapsed >= self._refresh_seconds

    async def refresh_if_stale(
        self,
        session: AsyncSession,
    ) -> CtInstanceSettings | None:
        """Refresh from DB only when the TTL has elapsed.

        Thread-safe via asyncio.Lock; concurrent coroutines wait for the
        first refresh rather than issuing duplicate DB queries.

        Args:
            session: Active async database session.

        Returns:
            The current settings row, or None if the table is empty.
        """
        if not self.is_stale():
            return self._cached
        async with self._lock:
            # Re-check after acquiring lock — another task may have refreshed.
            if not self.is_stale():
                return self._cached
            self._cached = await get_active_settings(session)
            self._last_refreshed = datetime.now(UTC)
        return self._cached

    async def force_refresh(
        self,
        session: AsyncSession,
    ) -> CtInstanceSettings | None:
        """Unconditionally refresh from DB and reset the TTL.

        Args:
            session: Active async database session.

        Returns:
            The current settings row, or None if the table is empty.
        """
        async with self._lock:
            self._cached = await get_active_settings(session)
            self._last_refreshed = datetime.now(UTC)
        return self._cached
