"""extend_log_backfill_state_with_retry_budget

Adds per-log retry-budget and error-counter columns to
``ct_log_backfill_state`` so the per-log path can implement self-healing
retry budgets, rate-limit cooldowns, and richer dashboard surfaces
without introducing audit/repair workflow.

Revision ID: a1b2c3d4e5f7
Revises: f4a5b6c7d8e9
Create Date: 2026-05-09 02:00:00.000000
"""

from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a1b2c3d4e5f7"
down_revision: str | None = "f4a5b6c7d8e9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "ct_log_backfill_state",
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "ct_log_backfill_state",
        sa.Column(
            "retryable_error_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "ct_log_backfill_state",
        sa.Column(
            "terminal_error_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "ct_log_backfill_state",
        sa.Column("last_error_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "ct_log_backfill_state",
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "ct_log_backfill_state",
        sa.Column("rate_limited_until", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("ct_log_backfill_state", "rate_limited_until")
    op.drop_column("ct_log_backfill_state", "next_retry_at")
    op.drop_column("ct_log_backfill_state", "last_error_at")
    op.drop_column("ct_log_backfill_state", "terminal_error_count")
    op.drop_column("ct_log_backfill_state", "retryable_error_count")
    op.drop_column("ct_log_backfill_state", "retry_count")
