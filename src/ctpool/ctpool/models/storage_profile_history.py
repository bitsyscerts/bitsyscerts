"""ORM model for the ``ct_storage_profile_history`` table.

One row per unique settings hash, recording every distinct storage-profile
configuration that has been active on this BitsysCerts instance.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from ctpool.models.base import Base


class CtStorageProfileHistory(Base):
    """Audit record of every distinct storage-profile configuration seen."""

    __tablename__ = "ct_storage_profile_history"
    __table_args__ = (
        UniqueConstraint(
            "settings_hash",
            name="uq_ct_storage_profile_history_settings_hash",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    settings_hash: Mapped[str] = mapped_column(Text, nullable=False)
    storage_profile: Mapped[str] = mapped_column(Text, nullable=False)
    cert_storage_mode: Mapped[str] = mapped_column(Text, nullable=False)
    hostname_retention_mode: Mapped[str] = mapped_column(Text, nullable=False)
    backfill_days: Mapped[int] = mapped_column(Integer, nullable=False)
    cert_retention_days: Mapped[int] = mapped_column(Integer, nullable=False)
    observation_retention_days: Mapped[int] = mapped_column(Integer, nullable=False)
    entry_outcome_retention_days: Mapped[int] = mapped_column(Integer, nullable=False)
    metrics_retention_days: Mapped[int] = mapped_column(Integer, nullable=False)
    raw_settings_json: Mapped[str] = mapped_column(Text, nullable=False)
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
    is_current: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
