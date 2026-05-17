"""Fix NULLS order on hostname sort and composite indexes.

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-05-17 00:00:00.000000

Migration c3d4e5f6a7b8 was deployed with the wrong NULLS ordering on all four
hostname indexes.  PostgreSQL's ``DESC`` shorthand means ``DESC NULLS FIRST``,
but the queries use ``ORDER BY col DESC NULLS LAST`` (SQLAlchemy
``desc(col).nullslast()``).  A NULLS-order mismatch prevents the planner from
using an index to satisfy the sort, forcing it to materialise every matching
row and sort in memory — which exceeds the 30-second statement timeout for
large registrable domains (e.g. amazonaws.com).

This migration drops the four affected indexes and recreates them with the
explicit ``DESC NULLS LAST`` / ``ASC NULLS FIRST`` ordering that matches the
query layer exactly.  The composite index sort direction also means one index
covers both ASC and DESC queries for the same column via forward/backward scan.
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "d4e5f6a7b8c9"
down_revision = "c3d4e5f6a7b8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Drop and recreate all four hostname indexes with correct NULLS ordering."""
    with op.get_context().autocommit_block():
        # Drop old indexes (may have wrong NULLS order from a previous deploy).
        op.execute(
            "DROP INDEX CONCURRENTLY IF EXISTS ix_hostnames_latest_cert_not_before"
        )
        op.execute(
            "DROP INDEX CONCURRENTLY IF EXISTS ix_hostnames_latest_cert_not_after"
        )
        op.execute(
            "DROP INDEX CONCURRENTLY IF EXISTS idx_hostnames_reg_domain_not_before"
        )
        op.execute(
            "DROP INDEX CONCURRENTLY IF EXISTS idx_hostnames_reg_domain_not_after"
        )

        # Sort-only indexes: used when no registrable_domain filter is present.
        op.execute(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS"
            " ix_hostnames_latest_cert_not_before"
            " ON hostnames (latest_cert_not_before DESC NULLS LAST, id DESC)"
        )
        op.execute(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS"
            " ix_hostnames_latest_cert_not_after"
            " ON hostnames (latest_cert_not_after DESC NULLS LAST, id DESC)"
        )

        # Composite indexes: forward scan → DESC NULLS LAST (most common sort);
        # backward scan → ASC NULLS FIRST.  One index per column covers both
        # sort directions for registrable-domain filtered queries.
        op.execute(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS"
            " idx_hostnames_reg_domain_not_before"
            " ON hostnames"
            " (registrable_domain, latest_cert_not_before DESC NULLS LAST, id DESC)"
        )
        op.execute(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS"
            " idx_hostnames_reg_domain_not_after"
            " ON hostnames"
            " (registrable_domain, latest_cert_not_after DESC NULLS LAST, id DESC)"
        )


def downgrade() -> None:
    """Restore the previous (incorrectly ordered) indexes."""
    with op.get_context().autocommit_block():
        op.execute(
            "DROP INDEX CONCURRENTLY IF EXISTS ix_hostnames_latest_cert_not_before"
        )
        op.execute(
            "DROP INDEX CONCURRENTLY IF EXISTS ix_hostnames_latest_cert_not_after"
        )
        op.execute(
            "DROP INDEX CONCURRENTLY IF EXISTS idx_hostnames_reg_domain_not_before"
        )
        op.execute(
            "DROP INDEX CONCURRENTLY IF EXISTS idx_hostnames_reg_domain_not_after"
        )
        op.execute(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS"
            " ix_hostnames_latest_cert_not_before"
            " ON hostnames (latest_cert_not_before DESC, id DESC)"
        )
        op.execute(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS"
            " ix_hostnames_latest_cert_not_after"
            " ON hostnames (latest_cert_not_after DESC, id DESC)"
        )
        op.execute(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS"
            " idx_hostnames_reg_domain_not_before"
            " ON hostnames (registrable_domain, latest_cert_not_before, id)"
        )
        op.execute(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS"
            " idx_hostnames_reg_domain_not_after"
            " ON hostnames (registrable_domain, latest_cert_not_after, id)"
        )
