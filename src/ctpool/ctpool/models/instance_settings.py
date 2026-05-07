"""ORM model for the ``ct_instance_settings`` table.

Stores the single active runtime storage profile for this BitsysCerts
instance.  At most one row should be active at any time; reads always
return the row with the most-recent ``updated_at``.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Integer, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from ctpool.models.base import Base


class CtInstanceSettings(Base):
    """Active runtime storage profile for this BitsysCerts instance."""

    __tablename__ = "ct_instance_settings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    storage_profile: Mapped[str] = mapped_column(Text, nullable=False)
    cert_storage_mode: Mapped[str] = mapped_column(Text, nullable=False)
    hostname_retention_mode: Mapped[str] = mapped_column(Text, nullable=False)
    backfill_days: Mapped[int] = mapped_column(Integer, nullable=False)
    cert_retention_days: Mapped[int] = mapped_column(Integer, nullable=False)
    observation_retention_days: Mapped[int] = mapped_column(Integer, nullable=False)
    entry_outcome_retention_days: Mapped[int] = mapped_column(Integer, nullable=False)
    metrics_retention_days: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
        onupdate=text("now()"),
    )
    updated_by: Mapped[str | None] = mapped_column(Text, nullable=True)
    settings_hash: Mapped[str] = mapped_column(Text, nullable=False)
    settings_json: Mapped[dict] = mapped_column(JSONB, nullable=False)  # type: ignore[type-arg]
