"""Autovacuum tuning for high-churn CT tables.

These two tables receive the highest write and delete volume in the system:

* ``ct_log_observations``  — one row per CT log entry ingested
* ``ct_entry_outcomes``    — one row per processed CT log entry

At default autovacuum scale factors (vacuum at 20%, analyze at 10%) Postgres
delays dead-tuple collection until 20% of the table has changed, which at
CT scale can mean tens of millions of dead tuples and severe bloat.

Setting ``autovacuum_vacuum_scale_factor=0.01`` (1%) and
``autovacuum_analyze_scale_factor=0.005`` (0.5%) triggers more frequent
vacuums and analyze runs, keeping the dead-tuple ratio and planner
statistics accurate even under sustained high-churn ingestion.

This migration is safe inside a transaction; ``ALTER TABLE … SET (…)``
changes storage parameters and does not lock the table for reads or writes.

Revision ID: a1b2c3d4e5f6
Revises: bf7738a16f18
Create Date: 2026-05-16
"""

from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision = "a1b2c3d4e5f6"
down_revision = "bf7738a16f18"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Apply tighter autovacuum thresholds to the two highest-churn tables."""
    op.execute(
        """
        ALTER TABLE ct_log_observations SET (
            autovacuum_vacuum_scale_factor = 0.01,
            autovacuum_analyze_scale_factor = 0.005
        )
        """
    )
    op.execute(
        """
        ALTER TABLE ct_entry_outcomes SET (
            autovacuum_vacuum_scale_factor = 0.01,
            autovacuum_analyze_scale_factor = 0.005
        )
        """
    )


def downgrade() -> None:
    """Restore default autovacuum thresholds (resets to Postgres defaults)."""
    op.execute(
        """
        ALTER TABLE ct_log_observations RESET (
            autovacuum_vacuum_scale_factor,
            autovacuum_analyze_scale_factor
        )
        """
    )
    op.execute(
        """
        ALTER TABLE ct_entry_outcomes RESET (
            autovacuum_vacuum_scale_factor,
            autovacuum_analyze_scale_factor
        )
        """
    )
