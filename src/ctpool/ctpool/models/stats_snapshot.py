"""ORM model for the ``ct_stats_snapshots`` table.

One row per computed stats snapshot.  The ``payload_json`` column holds the
full serialised ``StatsResponse`` dict so the API can return it without
re-running expensive live queries.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Integer, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from ctpool.models.base import Base


class CtStatsSnapshot(Base):
    """One persisted stats payload snapshot."""

    __tablename__ = "ct_stats_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    snapshot_type: Mapped[str] = mapped_column(Text, nullable=False)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    payload_json: Mapped[dict] = mapped_column(JSONB, nullable=False)  # type: ignore[type-arg]
