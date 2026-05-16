"""Add sort indexes on hostnames.latest_cert_not_before and _not_after.

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2025-01-01 00:00:00.000000

CREATE INDEX CONCURRENTLY cannot run inside a transaction block.  The correct
Alembic pattern is ``op.get_context().autocommit_block()`` which ends the
outer transaction, executes the statement in autocommit mode, and works with
both sync and async (psycopg) drivers.  The previous ``op.execute("COMMIT")``
trick does not work with the async driver because SQLAlchemy still holds an
open transaction context at the connection level.
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "b2c3d4e5f6a7"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create sort indexes for hostname keyset-pagination sort columns."""
    with op.get_context().autocommit_block():
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


def downgrade() -> None:
    """Drop sort indexes added in upgrade."""
    with op.get_context().autocommit_block():
        op.execute(
            "DROP INDEX CONCURRENTLY IF EXISTS ix_hostnames_latest_cert_not_before"
        )
        op.execute(
            "DROP INDEX CONCURRENTLY IF EXISTS ix_hostnames_latest_cert_not_after"
        )
