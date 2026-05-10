"""add_ct_maintenance_runs

Revision ID: b3c4d5e6f7a8
Revises: a1b2c3d4e5f7
Create Date: 2026-05-09 00:00:00.000000

Adds the ``ct_maintenance_runs`` audit table that records every invocation
of ``ctpool prune-for-storage-profile`` (and the maintenance loop), and
adds the ``idx_ct_maintenance_runs_started_at`` index used by the stats
projection to find the most recent run quickly.

Also adds the ``idx_hostnames_latest_cert_fingerprint`` index referenced
by Sprint 4 retention enforcement (used to confirm a candidate certificate
is not the latest evidence for any hostname).
"""

from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b3c4d5e6f7a8"
down_revision: str | None = "a1b2c3d4e5f7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create ct_maintenance_runs and supporting indexes."""
    op.create_table(
        "ct_maintenance_runs",
        sa.Column(
            "id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "run_type",
            sa.Text,
            nullable=False,
            server_default=sa.text("'prune_for_storage_profile'"),
        ),
        sa.Column("mode", sa.Text, nullable=False),
        sa.Column(
            "status",
            sa.Text,
            nullable=False,
            server_default=sa.text("'running'"),
        ),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Integer, nullable=True),
        sa.Column("storage_profile", sa.Text, nullable=True),
        sa.Column("settings_hash", sa.Text, nullable=True),
        sa.Column(
            "deleted_certificates",
            sa.BigInteger,
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "deleted_certificate_hostnames",
            sa.BigInteger,
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "deleted_observations",
            sa.BigInteger,
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "deleted_entry_outcomes",
            sa.BigInteger,
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "deleted_ingestion_metrics",
            sa.BigInteger,
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "preserved_hostnames",
            sa.BigInteger,
            nullable=True,
        ),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column(
            "details_json",
            sa.dialects.postgresql.JSONB,
            nullable=True,
        ),
        sa.CheckConstraint(
            "mode IN ('dry_run', 'execute')",
            name="ck_ct_maintenance_runs_mode",
        ),
        sa.CheckConstraint(
            "status IN ('running', 'complete', 'failed')",
            name="ck_ct_maintenance_runs_status",
        ),
    )
    op.create_index(
        "idx_ct_maintenance_runs_started_at",
        "ct_maintenance_runs",
        [sa.text("started_at DESC")],
    )
    op.create_index(
        "idx_ct_maintenance_runs_run_type_started_at",
        "ct_maintenance_runs",
        ["run_type", sa.text("started_at DESC")],
    )

    # Hostname latest-cert lookup (used by certificate prune safety check).
    conn = op.get_bind()
    has_hostnames = conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.tables WHERE table_name = 'hostnames'"
        )
    ).scalar()
    if has_hostnames:
        exists = conn.execute(
            sa.text("SELECT 1 FROM pg_indexes WHERE indexname = :name"),
            {"name": "idx_hostnames_latest_cert_fingerprint"},
        ).scalar()
        if not exists:
            op.create_index(
                "idx_hostnames_latest_cert_fingerprint",
                "hostnames",
                ["latest_cert_fingerprint_sha256"],
            )


def downgrade() -> None:
    """Drop ct_maintenance_runs and the hostname latest-cert index."""
    op.drop_index(
        "idx_hostnames_latest_cert_fingerprint",
        table_name="hostnames",
        if_exists=True,
    )
    op.drop_index(
        "idx_ct_maintenance_runs_run_type_started_at",
        table_name="ct_maintenance_runs",
        if_exists=True,
    )
    op.drop_index(
        "idx_ct_maintenance_runs_started_at",
        table_name="ct_maintenance_runs",
        if_exists=True,
    )
    op.drop_table("ct_maintenance_runs")
