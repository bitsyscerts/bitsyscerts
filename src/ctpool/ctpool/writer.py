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
from ctpool.entry_write_result import EntryWriteMetrics
from ctpool.observation_writer import upsert_observation
from ctpool.pipeline_schemas import NormalizedEntry

_logger = logging.getLogger(__name__)


async def write_normalized_entry(
    session: AsyncSession,
    entry: NormalizedEntry,
) -> EntryWriteMetrics:
    """Persist a fully parsed and normalized CT log entry to the database.

    Steps:
    1. Upsert the ``Certificate`` row (deduplicated by fingerprint_sha256).
    2. Upsert each hostname and the ``CertificateHostname`` join row.
    3. Upsert the ``CtLogObservation`` row (deduplicated by log_source_id + log_index).

    Args:
        session: Active async database session.
        entry:   Normalized CT log entry ready for persistence.

    Returns:
        Per-entry metrics derived from the exact certificate and hostname
        upsert outcomes for this stored entry.
    """
    observed_at = datetime.now(UTC)
    certificate_result = await upsert_certificate(
        session, entry.parsed_certificate, entry.is_wildcard_present
    )
    new_unique_hostnames = 0
    for hostname in entry.hostnames:
        hostname_result = await upsert_hostname(
            session,
            hostname,
            entry.parsed_certificate,
            observed_at=observed_at,
        )
        if hostname_result.inserted:
            new_unique_hostnames += 1
        await upsert_certificate_hostname(
            session,
            certificate_result.certificate_id,
            hostname_result.hostname_id,
        )
    await upsert_observation(
        session,
        entry.log_source_id,
        entry.log_index,
        certificate_result.certificate_id,
    )
    _logger.debug(
        "wrote entry log_source=%s index=%d cert=%s",
        entry.log_source_id,
        entry.log_index,
        entry.parsed_certificate.fingerprint_sha256[:16],
    )
    return EntryWriteMetrics.from_persisted_entry(
        certificate_inserted=certificate_result.inserted,
        hostnames_observed=len(entry.hostnames),
        new_unique_hostnames=new_unique_hostnames,
    )
