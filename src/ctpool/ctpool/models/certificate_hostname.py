"""ORM model for the ``certificate_hostnames`` many-to-many join table."""

from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from ctpool.models.base import Base


class CertificateHostname(Base):
    """Join table linking certificates to the hostnames they contain."""

    __tablename__ = "certificate_hostnames"

    certificate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("certificates.id", ondelete="CASCADE"),
        primary_key=True,
    )
    hostname_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("hostnames.id", ondelete="CASCADE"),
        primary_key=True,
    )
