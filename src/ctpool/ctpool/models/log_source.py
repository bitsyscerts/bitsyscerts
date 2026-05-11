"""ORM model for the ``ct_log_sources`` table.

Stores CT log identity and metadata discovered from the Chrome CT log list.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ctpool.models.base import Base

if TYPE_CHECKING:
    from ctpool.models.log_runtime_state import CtLogRuntimeState
    from ctpool.models.log_tail_cursor import CtLogTailCursor
    from ctpool.models.log_tail_lease import CtLogTailLease


class CtLogSource(Base):
    """Metadata for a single Certificate Transparency log."""

    __tablename__ = "ct_log_sources"
    __table_args__ = (
        UniqueConstraint("url", name="uq_ct_log_sources_url"),
        UniqueConstraint("log_id_b64", name="uq_ct_log_sources_log_id_b64"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    log_id_b64: Mapped[str] = mapped_column(Text, nullable=False)
    operator_name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    public_key_b64: Mapped[str] = mapped_column(Text, nullable=False)
    log_state: Mapped[str] = mapped_column(Text, nullable=False)
    temporal_shard_start: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    temporal_shard_end: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    is_eligible_for_tail: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    is_eligible_for_backfill: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    source_list: Mapped[str] = mapped_column(Text, nullable=False)
    first_seen_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_synced_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships (back-populated from child models)
    runtime_state: Mapped[CtLogRuntimeState | None] = relationship(
        "CtLogRuntimeState", back_populates="log_source", uselist=False
    )
    tail_cursor: Mapped[CtLogTailCursor | None] = relationship(
        "CtLogTailCursor", back_populates="log_source", uselist=False
    )
    tail_lease: Mapped[CtLogTailLease | None] = relationship(
        "CtLogTailLease", back_populates="log_source", uselist=False
    )
