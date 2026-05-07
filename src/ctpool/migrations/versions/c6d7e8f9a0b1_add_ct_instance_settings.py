"""add_ct_instance_settings

Revision ID: c6d7e8f9a0b1
Revises: b4c5d6e7f8a9
Create Date: 2026-05-07 10:00:00.000000

Creates the ct_instance_settings table which stores the single active
runtime storage profile for this BitsysCerts instance.
"""

from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c6d7e8f9a0b1"
down_revision: str | None = "b4c5d6e7f8a9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ct_instance_settings",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("storage_profile", sa.Text(), nullable=False),
        sa.Column("cert_storage_mode", sa.Text(), nullable=False),
        sa.Column("hostname_retention_mode", sa.Text(), nullable=False),
        sa.Column("backfill_days", sa.Integer(), nullable=False),
        sa.Column("cert_retention_days", sa.Integer(), nullable=False),
        sa.Column("observation_retention_days", sa.Integer(), nullable=False),
        sa.Column("entry_outcome_retention_days", sa.Integer(), nullable=False),
        sa.Column("metrics_retention_days", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("updated_by", sa.Text(), nullable=True),
        sa.Column("settings_hash", sa.Text(), nullable=False),
        sa.Column(
            "settings_json",
            sa.dialects.postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ct_instance_settings")),
    )
    op.create_index(
        op.f("ix_ct_instance_settings_settings_hash"),
        "ct_instance_settings",
        ["settings_hash"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_ct_instance_settings_settings_hash"),
        table_name="ct_instance_settings",
    )
    op.drop_table("ct_instance_settings")
