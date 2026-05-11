"""add_ct_log_tail_leases

Creates the ct_log_tail_leases table used by the atomic tail log dispatcher.
One row per CT log; claimed_by is NULL when the log is available for a worker
to pick up.  A heartbeat column keeps the lease alive; stale leases are
reclaimed by reap_stale_tail_leases in dispatcher_tail.

Revision ID: d3e4f5a6b7c8
Revises: c4d5e6f7a8b9
Create Date: 2026-05-11 00:00:00.000000
"""

from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "d3e4f5a6b7c8"
down_revision: str | None = "c4d5e6f7a8b9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ct_log_tail_leases",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "log_source_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("claimed_by", sa.Text(), nullable=True),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("log_source_id", name="uq_ct_log_tail_leases_log_source_id"),
        sa.ForeignKeyConstraint(
            ["log_source_id"],
            ["ct_log_sources.id"],
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "ix_ct_log_tail_leases_claimed_by",
        "ct_log_tail_leases",
        ["claimed_by"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_ct_log_tail_leases_claimed_by", table_name="ct_log_tail_leases"
    )
    op.drop_table("ct_log_tail_leases")
