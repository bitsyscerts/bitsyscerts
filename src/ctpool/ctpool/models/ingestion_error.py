"""ORM model for the ``ingestion_errors`` table.

Stores per-log error records for debugging and monitoring. Error messages
must be sanitized before storage (no credentials or connection strings).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from ctpool.models.base import Base


class IngestionError(Base):
    """A single error event recorded during CT log ingestion."""

    __tablename__ = "ingestion_errors"

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
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    error_type: Mapped[str] = mapped_column(Text, nullable=False)
    error_message: Mapped[str] = mapped_column(Text, nullable=False)
    log_index: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    http_status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
