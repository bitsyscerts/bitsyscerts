"""add_ingestion_metric_uniqueness_counters

Revision ID: c4d5e6f7a8b9
Revises: b3c4d5e6f7a8
Create Date: 2026-05-09 00:00:00.000000

"""

from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c4d5e6f7a8b9"
down_revision: str | None = "b3c4d5e6f7a8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "ingestion_metrics",
        sa.Column(
            "new_unique_certificates",
            sa.BigInteger(),
            server_default=sa.text("0"),
            nullable=False,
        ),
    )
    op.add_column(
        "ingestion_metrics",
        sa.Column(
            "duplicate_certificates",
            sa.BigInteger(),
            server_default=sa.text("0"),
            nullable=False,
        ),
    )
    op.add_column(
        "ingestion_metrics",
        sa.Column(
            "new_unique_hostnames",
            sa.BigInteger(),
            server_default=sa.text("0"),
            nullable=False,
        ),
    )
    op.add_column(
        "ingestion_metrics",
        sa.Column(
            "known_hostnames",
            sa.BigInteger(),
            server_default=sa.text("0"),
            nullable=False,
        ),
    )
    op.add_column(
        "ingestion_metrics",
        sa.Column(
            "retryable_errors",
            sa.BigInteger(),
            server_default=sa.text("0"),
            nullable=False,
        ),
    )
    op.add_column(
        "ingestion_metrics",
        sa.Column(
            "terminal_entry_errors",
            sa.BigInteger(),
            server_default=sa.text("0"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("ingestion_metrics", "terminal_entry_errors")
    op.drop_column("ingestion_metrics", "retryable_errors")
    op.drop_column("ingestion_metrics", "known_hostnames")
    op.drop_column("ingestion_metrics", "new_unique_hostnames")
    op.drop_column("ingestion_metrics", "duplicate_certificates")
    op.drop_column("ingestion_metrics", "new_unique_certificates")
