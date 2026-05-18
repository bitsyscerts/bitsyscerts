"""Repository for ``ct_stats_snapshots`` table operations.

Responsibilities:
    - Insert a new snapshot row.
    - Fetch the latest snapshot by type.
    - Prune old snapshot rows beyond the retention window.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from ctpool.models.stats_snapshot import CtStatsSnapshot


class StatsSnapshotRepository:
    """Encapsulates all DB access for ``ct_stats_snapshots``."""

    async def insert_snapshot(
        self,
        session: AsyncSession,
        snapshot_type: str,
        payload: dict[str, Any],
        duration_ms: int,
    ) -> CtStatsSnapshot:
        """Persist a new stats snapshot and return the created row.

        Args:
            session: Active async SQLAlchemy session.
            snapshot_type: Logical label, e.g. ``"full"``.
            payload: Serialisable stats payload dict.
            duration_ms: Time taken to compute the snapshot in milliseconds.

        Returns:
            The newly created :class:`CtStatsSnapshot` row.
        """
        row = CtStatsSnapshot(
            snapshot_type=snapshot_type,
            generated_at=datetime.now(UTC),
            duration_ms=duration_ms,
            payload_json=payload,
        )
        session.add(row)
        await session.flush()
        return row

    async def get_latest_snapshot(
        self,
        session: AsyncSession,
        snapshot_type: str,
    ) -> dict[str, Any] | None:
        """Return the payload of the most recent snapshot of *snapshot_type*.

        Args:
            session: Active async SQLAlchemy session.
            snapshot_type: Logical label to filter by.

        Returns:
            The ``payload_json`` dict, or ``None`` when no row exists.
        """
        stmt = (
            select(CtStatsSnapshot)
            .where(CtStatsSnapshot.snapshot_type == snapshot_type)
            .order_by(CtStatsSnapshot.generated_at.desc())
            .limit(1)
        )
        result = await session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return None
        payload = row.payload_json
        if isinstance(payload, str):
            return json.loads(payload)
        return payload

    async def get_latest_snapshot_age_seconds(
        self,
        session: AsyncSession,
        snapshot_type: str,
    ) -> float | None:
        """Return seconds since the most recent snapshot was generated.

        Returns ``None`` when no snapshot exists for *snapshot_type*.
        """
        stmt = (
            select(CtStatsSnapshot.generated_at)
            .where(CtStatsSnapshot.snapshot_type == snapshot_type)
            .order_by(CtStatsSnapshot.generated_at.desc())
            .limit(1)
        )
        result = await session.execute(stmt)
        generated_at = result.scalar_one_or_none()
        if generated_at is None:
            return None
        now = datetime.now(UTC)
        return (now - generated_at.replace(tzinfo=UTC)).total_seconds()

    async def prune_old_snapshots(
        self,
        session: AsyncSession,
        retention_hours: int,
        snapshot_type: str | None = None,
    ) -> int:
        """Delete snapshot rows older than *retention_hours*.

        Args:
            session: Active async SQLAlchemy session.
            retention_hours: Rows older than this many hours are deleted.
            snapshot_type: When provided, only prune rows of this type.

        Returns:
            Number of rows deleted.
        """
        cutoff = datetime.now(UTC) - timedelta(hours=retention_hours)
        stmt = delete(CtStatsSnapshot).where(CtStatsSnapshot.generated_at < cutoff)
        if snapshot_type is not None:
            stmt = stmt.where(CtStatsSnapshot.snapshot_type == snapshot_type)
        result = await session.execute(stmt)
        return int(result.rowcount)  # type: ignore[attr-defined]
