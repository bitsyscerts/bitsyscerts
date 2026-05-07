"""Coordinate the full write pipeline for a single CT log entry.

Exports:
    write_normalized_entry — Persist cert, hostnames, join rows, and observation.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from ctpool.cert_writer import (
    upsert_certificate,
    upsert_certificate_hostname,
    upsert_hostname,
)
from ctpool.observation_writer import upsert_observation
from ctpool.pipeline_schemas import NormalizedEntry

_logger = logging.getLogger(__name__)


async def write_normalized_entry(
    session: AsyncSession,
    entry: NormalizedEntry,
) -> None:
    """Persist a fully parsed and normalized CT log entry to the database.

    Steps:
    1. Upsert the ``Certificate`` row (deduplicated by fingerprint_sha256).
    2. Upsert each hostname and the ``CertificateHostname`` join row.
    3. Upsert the ``CtLogObservation`` row (deduplicated by log_source_id + log_index).

    Args:
        session: Active async database session.
        entry:   Normalized CT log entry ready for persistence.
    """
    observed_at = datetime.now(UTC)
    certificate_id = await upsert_certificate(
        session, entry.parsed_certificate, entry.is_wildcard_present
    )
    for hostname in entry.hostnames:
        hostname_id = await upsert_hostname(
            session,
            hostname,
            entry.parsed_certificate,
            observed_at=observed_at,
        )
        await upsert_certificate_hostname(session, certificate_id, hostname_id)
    await upsert_observation(
        session,
        entry.log_source_id,
        entry.log_index,
        certificate_id,
    )
    _logger.debug(
        "wrote entry log_source=%s index=%d cert=%s",
        entry.log_source_id,
        entry.log_index,
        entry.parsed_certificate.fingerprint_sha256[:16],
    )
