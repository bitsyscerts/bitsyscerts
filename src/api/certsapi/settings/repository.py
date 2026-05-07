"""Database access layer for the storage settings API.

Wraps reads and writes to ct_instance_settings and
ct_storage_profile_history.
"""

from __future__ import annotations

from ctpool.models.instance_settings import CtInstanceSettings
from ctpool.models.storage_profile_history import CtStorageProfileHistory
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


class SettingsRepository:
    """Database access for storage settings read/write operations."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_active_settings(self) -> CtInstanceSettings | None:
        """Return the most-recently-updated settings row, or None."""
        result = await self._session.execute(
            select(CtInstanceSettings)
            .order_by(CtInstanceSettings.updated_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def save_settings(self, row: CtInstanceSettings) -> CtInstanceSettings:
        """Persist a new settings row and flush to the session.

        The caller is responsible for committing the transaction.

        Args:
            row: Fully-populated CtInstanceSettings ORM instance.

        Returns:
            The same row after session.add and flush.
        """
        self._session.add(row)
        await self._session.flush()
        return row

    async def get_settings_history(
        self,
        limit: int = 50,
    ) -> list[CtStorageProfileHistory]:
        """Return profile history rows ordered newest first.

        Args:
            limit: Maximum number of rows to return. Defaults to 50.

        Returns:
            List of CtStorageProfileHistory ORM objects.
        """
        result = await self._session.execute(
            select(CtStorageProfileHistory)
            .order_by(CtStorageProfileHistory.last_seen_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())
