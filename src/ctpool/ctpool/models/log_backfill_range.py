"""ORM model for the ``ct_log_backfill_ranges`` table.

Each row is one backfill work unit covering a contiguous range of log indices.
Multiple workers can claim different rows concurrently via
``SELECT FOR UPDATE SKIP LOCKED``.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from ctpool.models.base import Base


class CtLogBackfillRange(Base):
    """A single backfill work unit for a contiguous index range in a CT log."""

    __tablename__ = "ct_log_backfill_ranges"
    __table_args__ = (
        UniqueConstraint(
            "log_source_id",
            "start_index",
            "end_index",
            name="uq_ct_log_backfill_ranges_log_source_start_end",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    log_source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ct_log_sources.id", ondelete="CASCADE"),
        nullable=False,
    )
    start_index: Mapped[int] = mapped_column(BigInteger, nullable=False)
    end_index: Mapped[int] = mapped_column(BigInteger, nullable=False)
    next_index: Mapped[int] = mapped_column(BigInteger, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="pending")
    claimed_by: Mapped[str | None] = mapped_column(Text, nullable=True)
    claimed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
