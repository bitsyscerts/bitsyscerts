"""Upsert CtLogObservation rows idempotently.

Exports:
    upsert_observation — Record that a certificate was observed at a log index.
"""

from __future__ import annotations

import uuid

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from ctpool.models.observation import CtLogObservation


async def upsert_observation(
    session: AsyncSession,
    log_source_id: uuid.UUID,
    log_index: int,
    certificate_id: uuid.UUID,
) -> None:
    """Upsert a ``CtLogObservation`` row idempotently.

    On conflict (``(log_source_id, log_index)`` already exists) the row is
    left unchanged — the observation timestamp must not be overwritten.

    Args:
        session:        Active async database session.
        log_source_id:  UUID of the CT log this entry was fetched from.
        log_index:      Index of this entry in the CT log.
        certificate_id: UUID of the upserted certificate.
    """
    stmt = (
        pg_insert(CtLogObservation)
        .values(
            log_source_id=log_source_id,
            log_index=log_index,
            certificate_id=certificate_id,
        )
        .on_conflict_do_nothing(
            index_elements=["log_source_id", "log_index"],
        )
    )
    await session.execute(stmt)
