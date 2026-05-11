"""adaptive_backfill_window

Adds ``observed_oldest_not_before`` and ``window_extended_count`` to
``ct_log_backfill_state`` so workers can self-correct their backfill
window based on observed certificate ``not_before`` dates.

Revision ID: a1b2c3d4e5f6
Revises: f4a5b6c7d8e9
Create Date: 2026-05-11 00:00:00.000000
"""

from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: str | None = "f4a5b6c7d8e9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "ct_log_backfill_state",
        sa.Column(
            "observed_oldest_not_before",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.add_column(
        "ct_log_backfill_state",
        sa.Column(
            "window_extended_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )


def downgrade() -> None:
    op.drop_column("ct_log_backfill_state", "window_extended_count")
    op.drop_column("ct_log_backfill_state", "observed_oldest_not_before")
