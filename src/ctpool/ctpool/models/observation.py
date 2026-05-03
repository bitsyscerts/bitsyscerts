"""ORM model for the ``ct_log_observations`` table.

One row per unique (log, index) pair linking a certificate to where it was
observed in a specific CT log.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from ctpool.models.base import Base


class CtLogObservation(Base):
    """Records that a certificate was seen at a specific index in a CT log."""

    __tablename__ = "ct_log_observations"
    __table_args__ = (
        UniqueConstraint(
            "log_source_id",
            "log_index",
            name="uq_ct_log_observations_log_source_id_log_index",
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
    log_index: Mapped[int] = mapped_column(BigInteger, nullable=False)
    certificate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("certificates.id", ondelete="CASCADE"),
        nullable=False,
    )
    observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
