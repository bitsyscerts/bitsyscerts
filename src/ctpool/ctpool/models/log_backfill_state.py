"""ORM model for the ``ct_log_backfill_state`` table.

One row per CT log tracks per-log backfill ownership and progress checkpoint.
Workers claim a log before processing its backfill ranges, record progress
checkpoints, and release the claim on completion or expiry.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ctpool.models.base import Base


class CtLogBackfillState(Base):
    """Per-log backfill ownership and progress checkpoint."""

    __tablename__ = "ct_log_backfill_state"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    log_source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ct_log_sources.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    status: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'pending'")
    )
    claimed_by: Mapped[str | None] = mapped_column(Text, nullable=True)
    claimed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    heartbeat_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_checkpoint_index: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    backfill_start_index: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    backfill_end_index: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    last_error_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_error_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    next_retry_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    rate_limited_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    retry_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    retryable_error_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    terminal_error_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    details_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    observed_oldest_not_before: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    window_extended_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )

    log_source: Mapped[object] = relationship("CtLogSource", lazy="select")
