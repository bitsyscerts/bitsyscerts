"""ORM model for the ``ingestion_metrics`` table.

Stores periodic throughput snapshots per CT log for monitoring and stats.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, Numeric, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from ctpool.models.base import Base


class IngestionMetric(Base):
    """A single throughput snapshot for a CT log ingestion window."""

    __tablename__ = "ingestion_metrics"

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
    snapshot_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    window_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    entries_fetched: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    entries_parsed: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    certs_upserted: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    hostnames_upserted: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0
    )
    new_unique_certificates: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0
    )
    duplicate_certificates: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0
    )
    new_unique_hostnames: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0
    )
    known_hostnames: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    retryable_errors: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    terminal_entry_errors: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0
    )
    parse_errors: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    http_429_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    http_5xx_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    throughput_entries_per_sec: Mapped[float | None] = mapped_column(
        Numeric(precision=12, scale=4), nullable=True
    )
