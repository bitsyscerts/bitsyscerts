"""extend_ct_log_backfill_state_for_per_log_dispatch

Adds window bounds, structured error details, and JSON metadata to
``ct_log_backfill_state`` so it can serve as the source-of-truth for
per-log backfill dispatch.

Revision ID: f4a5b6c7d8e9
Revises: e3f4a5b6c7d8
Create Date: 2026-05-09 00:30:00.000000
"""

from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "f4a5b6c7d8e9"
down_revision: str | None = "e3f4a5b6c7d8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "ct_log_backfill_state",
        sa.Column("backfill_start_index", sa.BigInteger(), nullable=True),
    )
    op.add_column(
        "ct_log_backfill_state",
        sa.Column("backfill_end_index", sa.BigInteger(), nullable=True),
    )
    op.add_column(
        "ct_log_backfill_state",
        sa.Column(
            "details_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("ct_log_backfill_state", "details_json")
    op.drop_column("ct_log_backfill_state", "backfill_end_index")
    op.drop_column("ct_log_backfill_state", "backfill_start_index")
