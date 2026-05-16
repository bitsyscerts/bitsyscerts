"""Add sort indexes on hostnames.latest_cert_not_before and _not_after.

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2025-01-01 00:00:00.000000

CREATE INDEX CONCURRENTLY cannot run inside a transaction, so this migration
commits the implicit transaction first and runs without transactional DDL.
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "b2c3d4e5f6a7"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create sort indexes for hostname keyset-pagination sort columns."""
    op.execute("COMMIT")
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
    op.execute("COMMIT")
    op.execute("DROP INDEX CONCURRENTLY IF EXISTS ix_hostnames_latest_cert_not_before")
    op.execute("DROP INDEX CONCURRENTLY IF EXISTS ix_hostnames_latest_cert_not_after")
