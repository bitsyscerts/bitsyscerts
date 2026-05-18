"""Safe batched deletion of expired certificate rows.

Exports:
    delete_certificates_batch — Delete a batch of cert rows and return counts.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from ctpool.models.certificate import Certificate
from ctpool.models.certificate_hostname import CertificateHostname
from ctpool.models.observation import CtLogObservation


@dataclass
class DeletionCounts:
    """Row counts from one batched deletion."""

    deleted_certificates: int
    deleted_certificate_hostnames: int
    deleted_ct_observations: int


async def delete_certificates_batch(
    session: AsyncSession,
    cert_ids: list[uuid.UUID],
) -> DeletionCounts:
    """Delete the given certificates and their dependent rows.

    Deletes ``certificate_hostnames`` and ``ct_log_observations`` rows for the
    given certificates before deleting the certificate rows themselves.  All
    deletes happen in the same transaction (caller controls the transaction).

    Note: ``ct_log_observations`` has ``ondelete="CASCADE"`` on the FK to
    ``certificates``, but we delete explicitly here to obtain accurate counts.

    Args:
        session:  Active async database session (caller-managed transaction).
        cert_ids: Certificate UUIDs to delete; MUST already be safety-checked
                  by the caller (see ``find_prunable_certificate_ids``).

    Returns:
        Row counts for each affected table.
    """
    if not cert_ids:
        return DeletionCounts(0, 0, 0)

    id_list = list(cert_ids)

    # Delete join rows first.
    ch_result = await session.execute(
        delete(CertificateHostname).where(
            CertificateHostname.certificate_id.in_(id_list)
        )
    )
    ch_count: int = ch_result.rowcount  # type: ignore[attr-defined]

    # Delete observation rows.
    obs_result = await session.execute(
        delete(CtLogObservation).where(CtLogObservation.certificate_id.in_(id_list))
    )
    obs_count: int = obs_result.rowcount  # type: ignore[attr-defined]

    # Delete the certificate rows.
    cert_result = await session.execute(
        delete(Certificate).where(Certificate.id.in_(id_list))
    )
    cert_count: int = cert_result.rowcount  # type: ignore[attr-defined]

    return DeletionCounts(
        deleted_certificates=cert_count,
        deleted_certificate_hostnames=ch_count,
        deleted_ct_observations=obs_count,
    )
