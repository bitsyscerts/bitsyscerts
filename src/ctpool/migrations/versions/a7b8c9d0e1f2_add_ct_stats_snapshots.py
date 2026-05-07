"""add_ct_stats_snapshots

Revision ID: a7b8c9d0e1f2
Revises: f2a3b4c5d6e7
Create Date: 2026-05-07 10:00:00.000000

Create the ``ct_stats_snapshots`` table that stores periodic snapshots of
computed stats payloads so the API can serve cached results without running
expensive live queries on every request.
"""

from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a7b8c9d0e1f2"
down_revision: str | None = "c6d7e8f9a0b1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ct_stats_snapshots",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("snapshot_type", sa.Text(), nullable=False),
        sa.Column(
            "generated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_ct_stats_snapshots"),
    )
    op.create_index(
        "ix_ct_stats_snapshots_type_generated",
        "ct_stats_snapshots",
        ["snapshot_type", sa.text("generated_at DESC")],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_ct_stats_snapshots_type_generated",
        table_name="ct_stats_snapshots",
    )
    op.drop_table("ct_stats_snapshots")
