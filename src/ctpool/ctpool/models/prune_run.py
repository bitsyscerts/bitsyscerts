"""ORM model for the ``ct_prune_runs`` table.

One row per prune-expired-certs execution, recording the mode, scope,
candidate counts, blocked-cert counts, deletion counts, and final status.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Integer, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from ctpool.models.base import Base


class CtPruneRun(Base):
    """Audit record for one prune-expired-certs invocation."""

    __tablename__ = "ct_prune_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    mode: Mapped[str] = mapped_column(Text, nullable=False)
    cutoff: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    retention_days: Mapped[int] = mapped_column(Integer, nullable=False)
    candidate_certificates: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("0")
    )
    blocked_latest_certificates: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("0")
    )
    blocked_missing_summary: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("0")
    )
    deleted_certificates: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("0")
    )
    deleted_certificate_hostnames: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("0")
    )
    deleted_ct_observations: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("0")
    )
    status: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'running'")
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
