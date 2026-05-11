"""ORM model for the ``hostnames`` table.

One row per unique normalized FQDN observed in any CT certificate SAN.
"""

from __future__ import annotations

import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy import Boolean, DateTime, Index, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from ctpool.models.base import Base


class Hostname(Base):
    """A unique normalized hostname observed in a certificate SAN."""

    __tablename__ = "hostnames"
    __table_args__ = (
        UniqueConstraint("hostname", name="uq_hostnames_hostname"),
        Index(
            "ix_hostnames_hostname_trgm",
            sa.text("hostname gin_trgm_ops"),
            postgresql_using="gin",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    hostname: Mapped[str] = mapped_column(Text, nullable=False)
    registrable_domain: Mapped[str] = mapped_column(Text, nullable=False)
    is_wildcard: Mapped[bool] = mapped_column(Boolean, nullable=False)
    first_seen_ct: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_seen_ct: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    latest_cert_fingerprint_sha256: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )
    latest_cert_not_before: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    latest_cert_not_after: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    latest_cert_issuer_cn: Mapped[str | None] = mapped_column(Text, nullable=True)
    latest_cert_issuer_org: Mapped[str | None] = mapped_column(Text, nullable=True)
    latest_cert_subject_cn: Mapped[str | None] = mapped_column(Text, nullable=True)
    latest_cert_is_precert: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    latest_cert_seen_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
