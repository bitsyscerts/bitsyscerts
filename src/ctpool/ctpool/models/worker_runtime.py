"""ORM model for the ``ct_worker_runtime`` table.

Each row represents one active or recently-stopped worker process.
Workers register here on startup, heartbeat while running, and mark
themselves stopped on clean exit.  Rows with an expired ``last_heartbeat_at``
are considered stale and may be taken over by a new worker.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, DateTime, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from ctpool.models.base import Base


class CtWorkerRuntime(Base):
    """Operational telemetry row for one CT ingestion worker process."""

    __tablename__ = "ct_worker_runtime"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    worker_id: Mapped[str] = mapped_column(Text, nullable=False)
    worker_kind: Mapped[str] = mapped_column(Text, nullable=False)
    log_source_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    log_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    direction: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False)

    claimed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_heartbeat_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    stopped_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    current_index: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    last_successful_index: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    batch_start_index: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    batch_end_index: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    processed_entries: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("0")
    )
    stored_certificates: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("0")
    )
    duplicate_certificates: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("0")
    )
    observed_hostnames: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("0")
    )
    new_hostnames: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("0")
    )
    parse_errors: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("0")
    )
    retryable_errors: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("0")
    )
    terminal_errors: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("0")
    )

    last_error_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    details_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
