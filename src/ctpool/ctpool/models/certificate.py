"""ORM model for the ``certificates`` table.

One row per unique certificate or precertificate, deduplicated by
SHA-256 fingerprint of the DER encoding.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from ctpool.models.base import Base


class Certificate(Base):
    """A deduplicated X.509 certificate or precertificate."""

    __tablename__ = "certificates"
    __table_args__ = (
        UniqueConstraint(
            "fingerprint_sha256",
            name="uq_certificates_fingerprint_sha256",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    fingerprint_sha256: Mapped[str] = mapped_column(Text, nullable=False)
    spki_sha256: Mapped[str] = mapped_column(Text, nullable=False)
    serial_number: Mapped[str] = mapped_column(Text, nullable=False)
    issuer_dn: Mapped[str] = mapped_column(Text, nullable=False)
    issuer_common_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    issuer_organization: Mapped[str | None] = mapped_column(Text, nullable=True)
    subject_dn: Mapped[str] = mapped_column(Text, nullable=False)
    subject_common_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    not_before: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    not_after: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    signature_algorithm_oid: Mapped[str] = mapped_column(Text, nullable=False)
    signature_algorithm_name: Mapped[str] = mapped_column(Text, nullable=False)
    public_key_algorithm_oid: Mapped[str] = mapped_column(Text, nullable=False)
    public_key_algorithm_name: Mapped[str] = mapped_column(Text, nullable=False)
    public_key_bits_or_curve: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_precertificate: Mapped[bool] = mapped_column(Boolean, nullable=False)
    is_wildcard_present: Mapped[bool] = mapped_column(Boolean, nullable=False)
    san_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    first_seen_ct: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_seen_ct: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
