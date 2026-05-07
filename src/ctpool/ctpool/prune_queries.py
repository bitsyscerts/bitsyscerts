"""Database queries for the prune-expired-certs command.

Exports:
    count_prunable_certificates    — Count certs eligible for deletion.
    find_prunable_certificate_ids  — Return a batch of prunable cert IDs.
    count_blocked_latest           — Count certs blocked because they are
                                     latest-cert for at least one hostname.
    count_blocked_missing_summary  — Count certs blocked because hostname
                                     has no latest-cert fingerprint set.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ctpool.models.certificate import Certificate
from ctpool.models.hostname import Hostname


async def count_prunable_certificates(
    session: AsyncSession,
    cutoff: datetime,
) -> int:
    """Return count of certificates expired before *cutoff*.

    Args:
        session: Active async database session.
        cutoff:  Only certs with not_after < cutoff are candidates.
    """
    stmt = select(func.count()).select_from(
        select(Certificate.id).where(Certificate.not_after < cutoff).subquery()
    )
    return int((await session.execute(stmt)).scalar_one())


async def find_prunable_certificate_ids(
    session: AsyncSession,
    cutoff: datetime,
    batch_size: int,
) -> list[uuid.UUID]:
    """Return up to *batch_size* certificate IDs that are safe to prune.

    A certificate is safe to prune if:
    - Its not_after is before *cutoff*, AND
    - No hostname row references it as the latest cert
      (i.e. hostnames.latest_cert_fingerprint_sha256 does not match).

    Args:
        session:    Active async database session.
        cutoff:     Cutoff datetime; certs with not_after < cutoff are eligible.
        batch_size: Maximum IDs to return per call.

    Returns:
        List of certificate UUIDs safe to delete.
    """
    # Subquery: fingerprints currently pinned as latest cert by any hostname.
    pinned_fp_subq = select(Hostname.latest_cert_fingerprint_sha256).where(
        Hostname.latest_cert_fingerprint_sha256.isnot(None)
    )
    stmt = (
        select(Certificate.id)
        .where(Certificate.not_after < cutoff)
        .where(Certificate.fingerprint_sha256.not_in(pinned_fp_subq))
        .limit(batch_size)
    )
    rows = (await session.execute(stmt)).scalars().all()
    return [uuid.UUID(str(r)) for r in rows]


async def count_blocked_latest(
    session: AsyncSession,
    cutoff: datetime,
) -> int:
    """Return count of expired certs blocked because they are a hostname's latest.

    Args:
        session: Active async database session.
        cutoff:  Certs with not_after < cutoff are the candidate pool.
    """
    pinned_fp_subq = select(Hostname.latest_cert_fingerprint_sha256).where(
        Hostname.latest_cert_fingerprint_sha256.isnot(None)
    )
    stmt = select(func.count()).select_from(
        select(Certificate.id)
        .where(Certificate.not_after < cutoff)
        .where(Certificate.fingerprint_sha256.in_(pinned_fp_subq))
        .subquery()
    )
    return int((await session.execute(stmt)).scalar_one())


async def count_blocked_missing_summary(
    session: AsyncSession,
) -> int:
    """Return count of hostnames with no latest-cert fingerprint.

    These hostnames cannot be inspected for safety, so their certs are kept.

    Args:
        session: Active async database session.
    """
    stmt = select(func.count()).select_from(
        select(Hostname.id)
        .where(Hostname.latest_cert_fingerprint_sha256.is_(None))
        .subquery()
    )
    return int((await session.execute(stmt)).scalar_one())
