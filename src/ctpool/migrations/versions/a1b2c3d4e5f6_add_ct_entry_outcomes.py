"""add_ct_entry_outcomes

Revision ID: a1b2c3d4e5f6
Revises: 565f9fb02ce6
Create Date: 2026-05-07 00:00:00.000000

"""

from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a1b2c3d4e5f6"
down_revision: str | None = "565f9fb02ce6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ALLOWED_OUTCOMES = (
    "'parse_error', 'skipped_by_policy', 'stored', 'unsupported_entry_type'"
)


def upgrade() -> None:
    op.create_table(
        "ct_entry_outcomes",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "log_source_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("log_index", sa.BigInteger(), nullable=False),
        sa.Column("outcome", sa.Text(), nullable=False),
        sa.Column("certificate_fingerprint_sha256", sa.Text(), nullable=True),
        sa.Column("error_type", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("parser_version", sa.Text(), nullable=True),
        sa.Column("raw_entry_hash", sa.Text(), nullable=True),
        sa.Column(
            "first_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "attempt_count",
            sa.Integer(),
            server_default=sa.text("1"),
            nullable=False,
        ),
        sa.Column(
            "details_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.CheckConstraint(
            f"outcome IN ({_ALLOWED_OUTCOMES})",
            name="ck_ct_entry_outcomes_outcome",
        ),
        sa.ForeignKeyConstraint(
            ["log_source_id"],
            ["ct_log_sources.id"],
            name="fk_ct_entry_outcomes_log_source_id_ct_log_sources",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_ct_entry_outcomes"),
        sa.UniqueConstraint(
            "log_source_id",
            "log_index",
            name="uq_ct_entry_outcomes_log_source_id_log_index",
        ),
    )
    op.create_index(
        "ix_ct_entry_outcomes_log_source_id",
        "ct_entry_outcomes",
        ["log_source_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_ct_entry_outcomes_log_source_id",
        table_name="ct_entry_outcomes",
    )
    op.drop_table("ct_entry_outcomes")
