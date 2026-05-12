"""ORM model for the ``ct_maintenance_runs`` table.

One row per ``ctpool prune-for-storage-profile`` execution (and per
maintenance-loop cycle).  Records the active storage profile, the mode
(dry-run vs execute), per-table deletion counts, and a final status.

The stats projection reads the most recent row to surface retention
maintenance state on the dashboard.  See Sprint 4 design notes for the
full contract.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, CheckConstraint, DateTime, Integer, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from ctpool.models.base import Base


class CtMaintenanceRun(Base):
    """Audit record for one storage-profile prune / maintenance invocation."""

    __tablename__ = "ct_maintenance_runs"
    __table_args__ = (
        CheckConstraint(
            "mode IN ('dry_run', 'execute')",
            name="ck_ct_maintenance_runs_mode",
        ),
        CheckConstraint(
            "status IN ('running', 'complete', 'failed')",
            name="ck_ct_maintenance_runs_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    run_type: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'prune_for_storage_profile'")
    )
    mode: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'running'")
    )

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    storage_profile: Mapped[str | None] = mapped_column(Text, nullable=True)
    settings_hash: Mapped[str | None] = mapped_column(Text, nullable=True)

    deleted_certificates: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("0")
    )
    deleted_certificate_hostnames: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("0")
    )
    deleted_observations: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("0")
    )
    deleted_entry_outcomes: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("0")
    )
    deleted_ingestion_metrics: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("0")
    )
    preserved_hostnames: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    details_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
