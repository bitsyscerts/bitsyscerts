"""add_ct_worker_runtime

Creates ct_worker_runtime table for per-worker lifecycle tracking, heartbeats,
and operational telemetry.  Workers register here on startup and heartbeat
while alive.  Stale rows (heartbeat expired) signal crash recovery.

Revision ID: d2e3f4a5b6c7
Revises: c9d0e1f2a3b4
Create Date: 2026-05-09 00:00:00.000000

"""

from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "d2e3f4a5b6c7"
down_revision: str | None = "c9d0e1f2a3b4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ct_worker_runtime",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("worker_id", sa.Text(), nullable=False),
        sa.Column("worker_kind", sa.Text(), nullable=False),
        sa.Column("log_source_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("log_name", sa.Text(), nullable=True),
        sa.Column("direction", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "last_heartbeat_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "started_at",
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
        sa.Column("stopped_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("current_index", sa.BigInteger(), nullable=True),
        sa.Column("last_successful_index", sa.BigInteger(), nullable=True),
        sa.Column("batch_start_index", sa.BigInteger(), nullable=True),
        sa.Column("batch_end_index", sa.BigInteger(), nullable=True),
        sa.Column(
            "processed_entries",
            sa.BigInteger(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "stored_certificates",
            sa.BigInteger(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "duplicate_certificates",
            sa.BigInteger(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "observed_hostnames",
            sa.BigInteger(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "new_hostnames",
            sa.BigInteger(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "parse_errors",
            sa.BigInteger(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "retryable_errors",
            sa.BigInteger(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "terminal_errors",
            sa.BigInteger(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("last_error_type", sa.Text(), nullable=True),
        sa.Column("last_error_message", sa.Text(), nullable=True),
        sa.Column(
            "details_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.PrimaryKeyConstraint("id", name="pk_ct_worker_runtime"),
    )
    op.create_index(
        "ix_ct_worker_runtime_worker_kind_log_source_id_status",
        "ct_worker_runtime",
        ["worker_kind", "log_source_id", "status"],
        unique=False,
    )
    op.create_index(
        "ix_ct_worker_runtime_last_heartbeat_at",
        "ct_worker_runtime",
        ["last_heartbeat_at"],
        unique=False,
    )
    op.create_index(
        "ix_ct_worker_runtime_worker_id",
        "ct_worker_runtime",
        ["worker_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_ct_worker_runtime_worker_id",
        table_name="ct_worker_runtime",
    )
    op.drop_index(
        "ix_ct_worker_runtime_last_heartbeat_at",
        table_name="ct_worker_runtime",
    )
    op.drop_index(
        "ix_ct_worker_runtime_worker_kind_log_source_id_status",
        table_name="ct_worker_runtime",
    )
    op.drop_table("ct_worker_runtime")
