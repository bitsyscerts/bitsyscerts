"""ORM model for the shared DB contention control-state table."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Integer, Numeric, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from ctpool.models.base import Base


class CtDbContentionState(Base):
    """One shared controller-state row used by all ctpool runners."""

    __tablename__ = "ct_db_contention_state"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    scope: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        unique=True,
        default="global",
        server_default=text("'global'"),
    )
    pressure_ema: Mapped[float] = mapped_column(
        Numeric(precision=12, scale=6),
        nullable=False,
        default=0.0,
        server_default=text("0"),
    )
    extra_sleep_seconds: Mapped[float] = mapped_column(
        Numeric(precision=12, scale=3),
        nullable=False,
        default=0.0,
        server_default=text("0"),
    )
    batch_size_cap: Mapped[int | None] = mapped_column(Integer, nullable=True)
    healthy_streak: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
    total_retryable_errors: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=0,
        server_default=text("0"),
    )
    retry_window_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
    )
    retry_window_start_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
