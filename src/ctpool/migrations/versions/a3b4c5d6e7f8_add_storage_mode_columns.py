"""add_storage_mode_columns

Revision ID: a3b4c5d6e7f8
Revises: f2a3b4c5d6e7
Create Date: 2026-05-07 00:03:00.000000

Storage-profile schema changes:
- Make ct_log_observations.certificate_id nullable (supports 'none' cert mode).
- Add certificates.public_key_der BYTEA NULL.
- Add certificates.raw_der BYTEA NULL.
"""

from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a3b4c5d6e7f8"
down_revision: str | None = "f2a3b4c5d6e7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Allow ct_log_observations.certificate_id to be NULL for 'none' cert mode.
    op.alter_column(
        "ct_log_observations",
        "certificate_id",
        existing_type=sa.UUID(),
        nullable=True,
    )

    # Add optional binary blobs to certificates.
    op.add_column(
        "certificates",
        sa.Column("public_key_der", sa.LargeBinary(), nullable=True),
    )
    op.add_column(
        "certificates",
        sa.Column("raw_der", sa.LargeBinary(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("certificates", "raw_der")
    op.drop_column("certificates", "public_key_der")
    op.alter_column(
        "ct_log_observations",
        "certificate_id",
        existing_type=sa.UUID(),
        nullable=False,
    )
