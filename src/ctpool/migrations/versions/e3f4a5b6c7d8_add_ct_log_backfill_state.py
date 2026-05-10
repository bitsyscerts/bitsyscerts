"""add_ct_log_backfill_state

Creates ct_log_backfill_state table for per-log durable backfill ownership
and progress tracking.  One row per CT log.  Workers claim a log here before
processing; the claim is released on completion or expiry.

Revision ID: e3f4a5b6c7d8
Revises: d2e3f4a5b6c7
Create Date: 2026-05-09 00:00:00.000000

"""

from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "e3f4a5b6c7d8"
down_revision: str | None = "d2e3f4a5b6c7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ct_log_backfill_state",
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
        sa.Column(
            "status", sa.Text(), nullable=False, server_default=sa.text("'pending'")
        ),
        sa.Column("claimed_by", sa.Text(), nullable=True),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_checkpoint_index", sa.BigInteger(), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("last_error_type", sa.Text(), nullable=True),
        sa.Column("last_error_message", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["log_source_id"],
            ["ct_log_sources.id"],
            ondelete="CASCADE",
            name="fk_ct_log_backfill_state_log_source_id_ct_log_sources",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_ct_log_backfill_state"),
        sa.UniqueConstraint(
            "log_source_id",
            name="uq_ct_log_backfill_state_log_source_id",
        ),
    )
    op.create_index(
        "ix_ct_log_backfill_state_status",
        "ct_log_backfill_state",
        ["status"],
        unique=False,
    )
    op.create_index(
        "ix_ct_log_backfill_state_log_source_id",
        "ct_log_backfill_state",
        ["log_source_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_ct_log_backfill_state_log_source_id",
        table_name="ct_log_backfill_state",
    )
    op.drop_index(
        "ix_ct_log_backfill_state_status",
        table_name="ct_log_backfill_state",
    )
    op.drop_table("ct_log_backfill_state")
