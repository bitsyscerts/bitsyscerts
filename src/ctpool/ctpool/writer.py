"""Coordinate the full write pipeline for a single CT log entry.

Exports:
    write_normalized_entry — Persist cert, hostnames, join rows, and observation.
"""

from __future__ import annotations

import logging
import uuid
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
from ctpool.storage_modes import (
    CertificatePersistenceFlags,
    CertStorageMode,
    flags_for_mode,
)

_logger = logging.getLogger(__name__)

# Safe default: write cert metadata but no binary blobs.  Callers in the
# ingestion pipeline MUST pass flags derived from the active storage profile;
# this default only applies to callers that don't (e.g. tests, one-off tools).
_DEFAULT_FLAGS: CertificatePersistenceFlags = flags_for_mode(
    CertStorageMode.METADATA_SPKI
)


async def write_normalized_entry(
    session: AsyncSession,
    entry: NormalizedEntry,
    *,
    flags: CertificatePersistenceFlags = _DEFAULT_FLAGS,
) -> EntryWriteMetrics:
    """Persist a fully parsed and normalized CT log entry to the database.

    Steps:
    1. Upsert the ``Certificate`` row unless ``flags.skip_cert`` is set
       (e.g. ``cert_storage_mode=none`` on the LITE profile).
    2. Upsert each hostname and the ``CertificateHostname`` join row (join
       skipped when ``flags.skip_cert``; hostnames are always tracked).
    3. Upsert the ``CtLogObservation`` row (``certificate_id=None`` when
       cert writes are skipped).

    Args:
        session: Active async database session.
        entry:   Normalized CT log entry ready for persistence.
        flags:   Write-path flags derived from the active cert storage mode.

    Returns:
        Per-entry metrics derived from the exact certificate and hostname
        upsert outcomes for this stored entry.
    """
    # This function is ~40 lines (warning zone) — justified because the three
    # sequential async steps form one atomic unit-of-work and cannot be split
    # without inverting control flow in a way that obscures the transaction
    # boundary.  Resolve when hostname and observation writes are extracted to
    # separate coordinating helpers.
    observed_at = datetime.now(UTC)
    certificate_id: uuid.UUID | None = None
    certificate_inserted = False
    new_unique_hostnames = 0

    if not flags.skip_cert:
        certificate_result = await upsert_certificate(
            session, entry.parsed_certificate, entry.is_wildcard_present
        )
        certificate_id = certificate_result.certificate_id
        certificate_inserted = certificate_result.inserted

    for hostname in entry.hostnames:
        hostname_result = await upsert_hostname(
            session,
            hostname,
            entry.parsed_certificate,
            observed_at=observed_at,
        )
        if hostname_result.inserted:
            new_unique_hostnames += 1
        if not flags.skip_cert and certificate_id is not None:
            await upsert_certificate_hostname(
                session,
                certificate_id,
                hostname_result.hostname_id,
            )

    await upsert_observation(
        session,
        entry.log_source_id,
        entry.log_index,
        certificate_id,
    )
    _logger.debug(
        "wrote entry log_source=%s index=%d cert=%s skip_cert=%s",
        entry.log_source_id,
        entry.log_index,
        entry.parsed_certificate.fingerprint_sha256[:16],
        flags.skip_cert,
    )
    if flags.skip_cert:
        # Cert rows were intentionally skipped by the storage profile; there
        # is no "duplicate" — report 0 new and 0 duplicate certificates.
        return EntryWriteMetrics(
            hostnames_observed=len(entry.hostnames),
            new_unique_hostnames=new_unique_hostnames,
            known_hostnames=len(entry.hostnames) - new_unique_hostnames,
        )
    return EntryWriteMetrics.from_persisted_entry(
        certificate_inserted=certificate_inserted,
        hostnames_observed=len(entry.hostnames),
        new_unique_hostnames=new_unique_hostnames,
    )
