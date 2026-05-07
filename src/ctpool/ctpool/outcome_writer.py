"""Upsert functions for ``ct_entry_outcomes`` terminal accounting.

Exports:
    upsert_entry_outcome — Atomically insert or update a terminal outcome row
                           for one CT log index.
"""

from __future__ import annotations

import uuid

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from ctpool.models.entry_outcome import CtEntryOutcome


async def upsert_entry_outcome(
    session: AsyncSession,
    log_source_id: uuid.UUID,
    log_index: int,
    outcome: str,
    *,
    certificate_fingerprint_sha256: str | None = None,
    error_type: str | None = None,
    error_message: str | None = None,
    parser_version: str | None = None,
    raw_entry_hash: str | None = None,
) -> None:
    """Insert or update a terminal outcome row for one CT log index.

    On first insert, all provided fields are stored.  On conflict (i.e. the
    entry was processed before), ``last_seen_at`` is refreshed,
    ``attempt_count`` is incremented, and mutable fields (``outcome``,
    error fields, ``certificate_fingerprint_sha256``) are updated.  This
    allows a successful re-parse to overwrite a prior failure outcome.

    Must be called inside an active ``session.begin()`` block.

    Args:
        session:                         Active async database session with an
                                         open transaction.
        log_source_id:                   FK to ``ct_log_sources.id``.
        log_index:                       Zero-based index within the CT log.
        outcome:                         One of the ``OUTCOME_*`` constants.
        certificate_fingerprint_sha256:  SHA-256 hex of the DER cert (for
                                         ``stored`` outcomes).
        error_type:                      Exception class name (failure outcomes).
        error_message:                   Truncated exception message (≤ 500 chars).
        parser_version:                  Optional parser/decoder version tag.
        raw_entry_hash:                  Optional hex SHA-256 of the raw bytes.
    """
    stmt = (
        pg_insert(CtEntryOutcome)
        .values(
            log_source_id=log_source_id,
            log_index=log_index,
            outcome=outcome,
            certificate_fingerprint_sha256=certificate_fingerprint_sha256,
            error_type=error_type,
            error_message=error_message,
            parser_version=parser_version,
            raw_entry_hash=raw_entry_hash,
        )
        .on_conflict_do_update(
            index_elements=["log_source_id", "log_index"],
            set_={
                "outcome": outcome,
                "certificate_fingerprint_sha256": certificate_fingerprint_sha256,
                "error_type": error_type,
                "error_message": error_message,
                "last_seen_at": func.now(),
                "attempt_count": CtEntryOutcome.attempt_count + 1,
            },
        )
    )
    await session.execute(stmt)
