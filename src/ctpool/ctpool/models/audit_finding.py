"""ORM model for the ``ct_audit_findings`` table.

Each row records one gap or anomaly detected during an audit scan.  The repair
columns (``repair_action``, ``repair_details_json``, etc.) remain NULL until
``fix-audit-findings`` processes the finding.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Integer, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from ctpool.models.base import Base


class CtAuditFinding(Base):
    """A single CT audit finding (gap, anomaly, or repair observation)."""

    __tablename__ = "ct_audit_findings"
    __table_args__ = (
        Index(
            "idx_ct_audit_findings_status_severity",
            "status",
            "severity",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    log_source_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ct_log_sources.id", ondelete="SET NULL"),
        nullable=True,
    )
    finding_type: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'open'")
    )
    # Links to the range that caused / will repair this finding (circular FK;
    # resolved in migration via ALTER TABLE — use_alter on the range side).
    range_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ct_log_backfill_ranges.id", ondelete="SET NULL"),
        nullable=True,
    )
    start_index: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    end_index: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    missing_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    details_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    # Repair columns — populated by fix-audit-findings
    repair_action: Mapped[str | None] = mapped_column(Text, nullable=True)
    repair_details_json: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB, nullable=True
    )
    repair_attempted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    repair_attempt_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    resolved_by: Mapped[str | None] = mapped_column(Text, nullable=True)
