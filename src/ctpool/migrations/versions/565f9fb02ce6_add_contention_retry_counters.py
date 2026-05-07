"""add_contention_retry_counters

Revision ID: 565f9fb02ce6
Revises: c5d4f0f9a123
Create Date: 2026-05-07 00:00:00.000000

"""

from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "565f9fb02ce6"
down_revision: str | None = "c5d4f0f9a123"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "ct_db_contention_state",
        sa.Column(
            "total_retryable_errors",
            sa.BigInteger(),
            server_default=sa.text("0"),
            nullable=False,
        ),
    )
    op.add_column(
        "ct_db_contention_state",
        sa.Column(
            "retry_window_count",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
    )
    op.add_column(
        "ct_db_contention_state",
        sa.Column(
            "retry_window_start_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("ct_db_contention_state", "retry_window_start_at")
    op.drop_column("ct_db_contention_state", "retry_window_count")
    op.drop_column("ct_db_contention_state", "total_retryable_errors")
