"""ORM model for the ``ct_log_tail_leases`` table.

Tracks which worker holds the active tail-ingestion lease for each CT log
(one row per log).  A NULL ``claimed_by`` means the log is available.
The heartbeat column is updated by the worker each batch; stale leases are
reclaimed by ``reap_stale_tail_leases`` in dispatcher_tail.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ctpool.models.base import Base

if TYPE_CHECKING:
    from ctpool.models.log_source import CtLogSource


class CtLogTailLease(Base):
    """Persistent tail-ingestion lease for a single CT log.

    One row per log.  ``claimed_by`` holds the ``hostname:PID`` worker-id
    string while a worker is active; NULL when the log is free.
    """

    __tablename__ = "ct_log_tail_leases"

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
    claimed_by: Mapped[str | None] = mapped_column(Text, nullable=True)
    claimed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    heartbeat_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    log_source: Mapped[CtLogSource] = relationship(
        "CtLogSource", back_populates="tail_lease"
    )
