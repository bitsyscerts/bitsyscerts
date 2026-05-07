"""add_performance_indexes

Revision ID: b8c9d0e1f2a3
Revises: a7b8c9d0e1f2
Create Date: 2026-05-07 10:01:00.000000

Add targeted indexes for backfill status queries, entry-outcome lookups,
observation pruning, metrics retention, audit visibility, and snapshot
retrieval.  All created with IF NOT EXISTS guards to be idempotent.
"""

from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b8c9d0e1f2a3"
down_revision: str | None = "a7b8c9d0e1f2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_INDEXES = [
    # Backfill status and stale-claim queries
    ("idx_ct_log_backfill_ranges_status", "ct_log_backfill_ranges", ["status"]),
    (
        "idx_ct_log_backfill_ranges_log_status",
        "ct_log_backfill_ranges",
        ["log_source_id", "status"],
    ),
    (
        "idx_ct_log_backfill_ranges_status_heartbeat",
        "ct_log_backfill_ranges",
        ["status", "heartbeat_at"],
    ),
    # Entry-outcome lookup and audit queries
    (
        "idx_ct_entry_outcomes_log_index",
        "ct_entry_outcomes",
        ["log_source_id", "log_index"],
    ),
    ("idx_ct_entry_outcomes_outcome", "ct_entry_outcomes", ["outcome"]),
    ("idx_ct_entry_outcomes_processed_at", "ct_entry_outcomes", ["first_seen_at"]),
    # Observation retention and pruning
    ("idx_ct_log_observations_observed_at", "ct_log_observations", ["observed_at"]),
    (
        "idx_ct_log_observations_log_index",
        "ct_log_observations",
        ["log_source_id", "log_index"],
    ),
    # Metrics retention
    ("idx_ingestion_metrics_snapshot_at", "ingestion_metrics", ["snapshot_at"]),
    # Audit finding visibility
    (
        "idx_ct_audit_findings_status_severity",
        "ct_audit_findings",
        ["status", "severity"],
    ),
]


def upgrade() -> None:
    conn = op.get_bind()
    for idx_name, table_name, columns in _INDEXES:
        # Skip if the index already exists (idempotent)
        exists = conn.execute(
            sa.text("SELECT 1 FROM pg_indexes WHERE indexname = :name"),
            {"name": idx_name},
        ).scalar()
        if exists:
            continue
        op.create_index(idx_name, table_name, columns)


def downgrade() -> None:
    for idx_name, table_name, _ in _INDEXES:
        op.drop_index(idx_name, table_name=table_name, if_exists=True)
