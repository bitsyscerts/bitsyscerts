"""add_hostname_latest_cert_fields

Revision ID: e1f2a3b4c5d6
Revises: d1e2f3a4b5c6
Create Date: 2026-05-07 00:01:00.000000

Add enriched latest-cert summary columns to the ``hostnames`` table so that
each hostname row carries the issuer, subject, precert flag, and a timestamp
of when the latest-cert summary was last written.
"""

from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e1f2a3b4c5d6"
down_revision: str | None = "d1e2f3a4b5c6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "hostnames",
        sa.Column("latest_cert_issuer_cn", sa.Text(), nullable=True),
    )
    op.add_column(
        "hostnames",
        sa.Column("latest_cert_issuer_org", sa.Text(), nullable=True),
    )
    op.add_column(
        "hostnames",
        sa.Column("latest_cert_subject_cn", sa.Text(), nullable=True),
    )
    op.add_column(
        "hostnames",
        sa.Column("latest_cert_is_precert", sa.Boolean(), nullable=True),
    )
    op.add_column(
        "hostnames",
        sa.Column("latest_cert_seen_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("hostnames", "latest_cert_seen_at")
    op.drop_column("hostnames", "latest_cert_is_precert")
    op.drop_column("hostnames", "latest_cert_subject_cn")
    op.drop_column("hostnames", "latest_cert_issuer_org")
    op.drop_column("hostnames", "latest_cert_issuer_cn")
