"""add_ct_audit_findings_and_audit_cols

Creates the ct_audit_findings table (full schema: detection + repair columns)
and adds audit-support columns to ct_log_backfill_ranges:
  - last_error, attempt_count       (detection phase)
  - range_kind, repair_for_finding_id (repair phase, circular FK resolved
    with ALTER TABLE after both tables exist)

Revision ID: d1e2f3a4b5c6
Revises: b2c3d4e5f6a7
Create Date: 2026-05-20 00:00:00.000000

"""

from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "d1e2f3a4b5c6"
down_revision: str | None = "b2c3d4e5f6a7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # 1. Create ct_audit_findings (no range_id FK yet — circular reference
    #    is resolved in step 4 once ct_log_backfill_ranges also has its FK
    #    to this table).
    # ------------------------------------------------------------------
    op.create_table(
        "ct_audit_findings",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "log_source_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("ct_log_sources.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("finding_type", sa.Text(), nullable=False),
        sa.Column("severity", sa.Text(), nullable=False),
        sa.Column(
            "status",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'open'"),
        ),
        # range_id added via ALTER TABLE below (circular FK)
        sa.Column("start_index", sa.BigInteger(), nullable=True),
        sa.Column("end_index", sa.BigInteger(), nullable=True),
        sa.Column("missing_count", sa.Integer(), nullable=True),
        sa.Column("details_json", postgresql.JSONB(), nullable=True),
        # Repair columns (all nullable until a repair is attempted)
        sa.Column("repair_action", sa.Text(), nullable=True),
        sa.Column("repair_details_json", postgresql.JSONB(), nullable=True),
        sa.Column("repair_attempted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "repair_attempt_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_by", sa.Text(), nullable=True),
    )

    op.create_index(
        "ix_ct_audit_findings_status",
        "ct_audit_findings",
        ["status"],
    )
    op.create_index(
        "ix_ct_audit_findings_finding_type",
        "ct_audit_findings",
        ["finding_type"],
    )
    op.create_index(
        "ix_ct_audit_findings_log_source_id",
        "ct_audit_findings",
        ["log_source_id"],
    )

    # ------------------------------------------------------------------
    # 2. Add detection-phase columns to ct_log_backfill_ranges
    # ------------------------------------------------------------------
    op.add_column(
        "ct_log_backfill_ranges",
        sa.Column("last_error", sa.Text(), nullable=True),
    )
    op.add_column(
        "ct_log_backfill_ranges",
        sa.Column(
            "attempt_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )

    # ------------------------------------------------------------------
    # 3. Add repair-phase columns to ct_log_backfill_ranges
    #    range_kind defaults to 'backfill' for all existing rows.
    # ------------------------------------------------------------------
    op.add_column(
        "ct_log_backfill_ranges",
        sa.Column(
            "range_kind",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'backfill'"),
        ),
    )
    op.add_column(
        "ct_log_backfill_ranges",
        sa.Column(
            "repair_for_finding_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
    )

    # ------------------------------------------------------------------
    # 4. Resolve circular FK:
    #    ct_log_backfill_ranges.repair_for_finding_id → ct_audit_findings.id
    # ------------------------------------------------------------------
    op.create_foreign_key(
        "fk_ct_log_backfill_ranges_repair_for_finding_id",
        "ct_log_backfill_ranges",
        "ct_audit_findings",
        ["repair_for_finding_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # ------------------------------------------------------------------
    # 5. Add range_id column to ct_audit_findings + FK (other side of
    #    circular reference).
    # ------------------------------------------------------------------
    op.add_column(
        "ct_audit_findings",
        sa.Column(
            "range_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
    )
    op.create_foreign_key(
        "fk_ct_audit_findings_range_id",
        "ct_audit_findings",
        "ct_log_backfill_ranges",
        ["range_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # ------------------------------------------------------------------
    # 6. Partial unique index for idempotent repair range creation.
    # ------------------------------------------------------------------
    op.create_index(
        "uq_ct_log_backfill_ranges_repair_finding_span",
        "ct_log_backfill_ranges",
        ["repair_for_finding_id", "start_index", "end_index"],
        unique=True,
        postgresql_where=sa.text("repair_for_finding_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_ct_log_backfill_ranges_repair_finding_span",
        table_name="ct_log_backfill_ranges",
    )
    op.drop_constraint(
        "fk_ct_audit_findings_range_id",
        "ct_audit_findings",
        type_="foreignkey",
    )
    op.drop_column("ct_audit_findings", "range_id")
    op.drop_constraint(
        "fk_ct_log_backfill_ranges_repair_for_finding_id",
        "ct_log_backfill_ranges",
        type_="foreignkey",
    )
    op.drop_column("ct_log_backfill_ranges", "repair_for_finding_id")
    op.drop_column("ct_log_backfill_ranges", "range_kind")
    op.drop_column("ct_log_backfill_ranges", "attempt_count")
    op.drop_column("ct_log_backfill_ranges", "last_error")
    op.drop_index("ix_ct_audit_findings_log_source_id", table_name="ct_audit_findings")
    op.drop_index("ix_ct_audit_findings_finding_type", table_name="ct_audit_findings")
    op.drop_index("ix_ct_audit_findings_status", table_name="ct_audit_findings")
    op.drop_table("ct_audit_findings")
