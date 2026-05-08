"""add_write_error_outcome

Revision ID: c9d0e1f2a3b4
Revises: b8c9d0e1f2a3
Create Date: 2026-05-08 00:00:00.000000

Extend the CHECK constraint on ``ct_entry_outcomes.outcome`` to allow the
new ``write_error`` terminal outcome.  This outcome is recorded when a CT
log entry is parsed successfully but cannot be written to the database after
all deadlock/retry attempts are exhausted.

Previously the backfill worker silently dropped these entries — the range was
still marked ``complete`` but no outcome row existed for those indices,
causing the audit checker to raise ``missing_entry_outcomes`` findings on
every run.  Recording ``write_error`` closes that accounting gap: every
index in a completed range now has exactly one outcome row, and audit repair
re-queues any ``write_error`` spans for a clean re-fetch.
"""

from __future__ import annotations

from typing import Sequence

from alembic import op

revision: str = "c9d0e1f2a3b4"
down_revision: str | None = "b8c9d0e1f2a3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_OLD_CONSTRAINT = "outcome IN ('parse_error', 'skipped_by_policy', 'stored', 'unsupported_entry_type')"
_NEW_CONSTRAINT = (
    "outcome IN ("
    "'parse_error', 'skipped_by_policy', 'stored', "
    "'unsupported_entry_type', 'write_error'"
    ")"
)
_CONSTRAINT_NAME = "ck_ct_entry_outcomes_outcome"


def upgrade() -> None:
    op.drop_constraint(
        _CONSTRAINT_NAME,
        "ct_entry_outcomes",
        type_="check",
    )
    op.create_check_constraint(
        _CONSTRAINT_NAME,
        "ct_entry_outcomes",
        _NEW_CONSTRAINT,
    )


def downgrade() -> None:
    # Remove any write_error rows first so the old constraint can be restored
    # without a constraint violation.
    op.execute("DELETE FROM ct_entry_outcomes WHERE outcome = 'write_error'")
    op.drop_constraint(
        _CONSTRAINT_NAME,
        "ct_entry_outcomes",
        type_="check",
    )
    op.create_check_constraint(
        _CONSTRAINT_NAME,
        "ct_entry_outcomes",
        _OLD_CONSTRAINT,
    )
