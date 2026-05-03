"""ORM model for the ``ct_log_runtime_state`` table.

Tracks live health and adaptive behavior state for each CT log (one row per
log). Includes HTTP error counters, backoff timestamps, and adaptive batch
size.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ctpool.models.base import Base

if TYPE_CHECKING:
    from ctpool.models.log_source import CtLogSource


class CtLogRuntimeState(Base):
    """Live health and adaptive state for a single CT log."""

    __tablename__ = "ct_log_runtime_state"

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
    tree_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sth_timestamp: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    health_status: Mapped[str] = mapped_column(Text, nullable=False, default="unknown")
    last_probe_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_success_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_error_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    current_batch_size: Mapped[int] = mapped_column(
        Integer, nullable=False, default=256
    )
    learned_max_batch_size: Mapped[int] = mapped_column(
        Integer, nullable=False, default=256
    )
    backoff_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_429_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    consecutive_failures: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )

    log_source: Mapped[CtLogSource] = relationship(
        "CtLogSource", back_populates="runtime_state"
    )
