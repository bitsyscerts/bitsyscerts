"""Add composite indexes on hostnames for registrable_domain recursive search.

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2025-01-01 00:00:00.000000

Adds two B-tree composite indexes that allow the recursive hostname search
(``registrable_domain = ?``) to resolve the WHERE filter and the sort in a
single index scan, avoiding the heap-sort of all matching rows.

Prior behaviour used ``hostname LIKE '%.domain'`` which required the GIN
trigram index to enumerate all matching rows and then a full sort.  For large
registrable domains (e.g. cisco.com with 100 k+ subdomains) this regularly
exceeded the 30-second statement timeout.

CREATE INDEX CONCURRENTLY must run outside a transaction block.  Use
``op.get_context().autocommit_block()`` — this is the Alembic-supported
pattern for both sync and async (psycopg3) drivers.
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "c3d4e5f6a7b8"
down_revision = "b2c3d4e5f6a7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create composite registrable-domain + sort-column indexes."""
    with op.get_context().autocommit_block():
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
    """Drop composite registrable-domain indexes."""
    with op.get_context().autocommit_block():
        op.execute(
            "DROP INDEX CONCURRENTLY IF EXISTS idx_hostnames_reg_domain_not_before"
        )
        op.execute(
            "DROP INDEX CONCURRENTLY IF EXISTS idx_hostnames_reg_domain_not_after"
        )
