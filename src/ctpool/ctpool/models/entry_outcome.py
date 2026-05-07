"""ORM model for the ``ct_entry_outcomes`` table.

One row per unique (log_source_id, log_index) pair.  Records the terminal
outcome for every processed CT log index: stored, parse_error,
unsupported_entry_type, or skipped_by_policy.

This table is the durable accounting layer.  A tail cursor or backfill range
may only advance after every index in the processed span has a row here.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from ctpool.models.base import Base
from ctpool.outcome_constants import ALL_OUTCOMES

_ALLOWED_SQL = ", ".join(f"'{v}'" for v in sorted(ALL_OUTCOMES))


class CtEntryOutcome(Base):
    """Terminal processing outcome for one CT log index."""

    __tablename__ = "ct_entry_outcomes"
    __table_args__ = (
        UniqueConstraint(
            "log_source_id",
            "log_index",
            name="uq_ct_entry_outcomes_log_source_id_log_index",
        ),
        CheckConstraint(
            f"outcome IN ({_ALLOWED_SQL})",
            name="outcome",
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
    outcome: Mapped[str] = mapped_column(Text, nullable=False)
    certificate_fingerprint_sha256: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )
    error_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    parser_version: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_entry_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
    attempt_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("1"),
    )
    details_json: Mapped[dict | None] = mapped_column(  # type: ignore[type-arg]
        JSONB, nullable=True
    )
    storage_profile: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'unknown'")
    )
    cert_storage_mode: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'unknown'")
    )
    processed_settings_hash: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'unknown'")
    )
