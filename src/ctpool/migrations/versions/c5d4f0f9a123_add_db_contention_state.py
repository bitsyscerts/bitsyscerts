"""add_db_contention_state

Revision ID: c5d4f0f9a123
Revises: dab4963f165e
Create Date: 2026-05-06 19:05:00.000000

"""

from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c5d4f0f9a123"
down_revision: str | None = "dab4963f165e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ct_db_contention_state",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "scope",
            sa.Text(),
            server_default=sa.text("'global'"),
            nullable=False,
        ),
        sa.Column(
            "pressure_ema",
            sa.Numeric(precision=12, scale=6),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "extra_sleep_seconds",
            sa.Numeric(precision=12, scale=3),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column("batch_size_cap", sa.Integer(), nullable=True),
        sa.Column(
            "healthy_streak",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ct_db_contention_state")),
        sa.UniqueConstraint("scope", name=op.f("uq_ct_db_contention_state_scope")),
    )


def downgrade() -> None:
    op.drop_table("ct_db_contention_state")
