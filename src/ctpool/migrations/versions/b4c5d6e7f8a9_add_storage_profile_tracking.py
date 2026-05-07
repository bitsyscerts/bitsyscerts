"""add_storage_profile_tracking

Revision ID: b4c5d6e7f8a9
Revises: a3b4c5d6e7f8
Create Date: 2026-05-07 00:04:00.000000

Storage profile transition and reconciliation tracking:
- CREATE TABLE ct_storage_profile_history
- ALTER TABLE ct_entry_outcomes ADD COLUMNS: storage_profile, cert_storage_mode,
  processed_settings_hash
- ALTER TABLE ct_log_backfill_ranges ADD COLUMNS: reason,
  reconcile_for_settings_hash, reconcile_target_settings_hash
"""

from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b4c5d6e7f8a9"
down_revision: str | None = "a3b4c5d6e7f8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # --- ct_storage_profile_history ----------------------------------------
    op.create_table(
        "ct_storage_profile_history",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "settings_hash",
            sa.Text(),
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
            "raw_settings_json",
            sa.Text(),
            nullable=False,
        ),
        sa.Column(
            "first_seen_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "is_current",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ct_storage_profile_history")),
        sa.UniqueConstraint(
            "settings_hash",
            name=op.f("uq_ct_storage_profile_history_settings_hash"),
        ),
    )
    op.create_index(
        "ix_ct_storage_profile_history_is_current",
        "ct_storage_profile_history",
        ["is_current"],
    )

    # --- ct_entry_outcomes extra columns ------------------------------------
    op.add_column(
        "ct_entry_outcomes",
        sa.Column(
            "storage_profile",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'unknown'"),
        ),
    )
    op.add_column(
        "ct_entry_outcomes",
        sa.Column(
            "cert_storage_mode",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'unknown'"),
        ),
    )
    op.add_column(
        "ct_entry_outcomes",
        sa.Column(
            "processed_settings_hash",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'unknown'"),
        ),
    )
    op.create_index(
        "ix_ct_entry_outcomes_processed_settings_hash",
        "ct_entry_outcomes",
        ["processed_settings_hash"],
    )

    # --- ct_log_backfill_ranges extra columns --------------------------------
    op.add_column(
        "ct_log_backfill_ranges",
        sa.Column("reason", sa.Text(), nullable=True),
    )
    op.add_column(
        "ct_log_backfill_ranges",
        sa.Column("reconcile_for_settings_hash", sa.Text(), nullable=True),
    )
    op.add_column(
        "ct_log_backfill_ranges",
        sa.Column("reconcile_target_settings_hash", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("ct_log_backfill_ranges", "reconcile_target_settings_hash")
    op.drop_column("ct_log_backfill_ranges", "reconcile_for_settings_hash")
    op.drop_column("ct_log_backfill_ranges", "reason")
    op.drop_index(
        "ix_ct_entry_outcomes_processed_settings_hash",
        table_name="ct_entry_outcomes",
    )
    op.drop_column("ct_entry_outcomes", "processed_settings_hash")
    op.drop_column("ct_entry_outcomes", "cert_storage_mode")
    op.drop_column("ct_entry_outcomes", "storage_profile")
    op.drop_index(
        "ix_ct_storage_profile_history_is_current",
        table_name="ct_storage_profile_history",
    )
    op.drop_table("ct_storage_profile_history")
