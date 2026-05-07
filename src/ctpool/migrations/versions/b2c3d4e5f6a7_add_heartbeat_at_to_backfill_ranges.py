"""add_heartbeat_at_to_backfill_ranges

Adds heartbeat_at to ct_log_backfill_ranges so the stale-claim reaper can
distinguish dead workers from live long-running ones.

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-05-07 00:00:00.000000

"""

from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b2c3d4e5f6a7"
down_revision: str | None = "a1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "ct_log_backfill_ranges",
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_ct_log_backfill_ranges_status",
        "ct_log_backfill_ranges",
        ["status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_ct_log_backfill_ranges_status",
        table_name="ct_log_backfill_ranges",
    )
    op.drop_column("ct_log_backfill_ranges", "heartbeat_at")
