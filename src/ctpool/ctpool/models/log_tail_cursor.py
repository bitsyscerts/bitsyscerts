"""ORM model for the ``ct_log_tail_cursors`` table.

Tracks tail worker progress for each CT log (one row per log). The
``next_index`` column records the next log index the tail worker should fetch.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, DateTime, ForeignKey, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ctpool.models.base import Base

if TYPE_CHECKING:
    from ctpool.models.log_source import CtLogSource


class CtLogTailCursor(Base):
    """Tail worker progress cursor for a single CT log."""

    __tablename__ = "ct_log_tail_cursors"

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
    next_index: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    log_source: Mapped[CtLogSource] = relationship(
        "CtLogSource", back_populates="tail_cursor"
    )
