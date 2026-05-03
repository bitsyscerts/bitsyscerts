"""Upsert Certificate, Hostname, and CertificateHostname rows idempotently.

Exports:
    upsert_certificate         — Upsert a certificate row; return its id.
    upsert_hostname            — Upsert a hostname row; return its id.
    upsert_certificate_hostname — Ensure the M2M join row exists.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from ctpool.models.certificate import Certificate
from ctpool.models.certificate_hostname import CertificateHostname
from ctpool.models.hostname import Hostname
from ctpool.normalizer import extract_registrable_domain
from ctpool.pipeline_schemas import ParsedCertificate


async def upsert_certificate(
    session: AsyncSession,
    parsed: ParsedCertificate,
    is_wildcard_present: bool,
) -> uuid.UUID:
    """Upsert a ``Certificate`` row and return its ``id``.

    On conflict (``fingerprint_sha256`` already exists) the row is updated with
    the latest ``last_seen_ct`` timestamp and wildcard/SAN metadata.

    Args:
        session:            Active async database session.
        parsed:             Validated certificate data from the parser.
        is_wildcard_present: True if any SAN contains a wildcard.

    Returns:
        The ``id`` of the upserted certificate.
    """
    now = datetime.now(UTC)
    stmt = (
        pg_insert(Certificate)
        .values(
            fingerprint_sha256=parsed.fingerprint_sha256,
            spki_sha256=parsed.spki_sha256,
            serial_number=parsed.serial_number,
            issuer_dn=parsed.issuer_dn,
            issuer_common_name=parsed.issuer_common_name,
            issuer_organization=parsed.issuer_organization,
            subject_dn=parsed.subject_dn,
            subject_common_name=parsed.subject_common_name,
            not_before=parsed.not_before,
            not_after=parsed.not_after,
            signature_algorithm_oid=parsed.signature_algorithm_oid,
            signature_algorithm_name=parsed.signature_algorithm_name,
            public_key_algorithm_oid=parsed.public_key_algorithm_oid,
            public_key_algorithm_name=parsed.public_key_algorithm_name,
            public_key_bits_or_curve=parsed.public_key_bits_or_curve,
            is_precertificate=parsed.is_precertificate,
            is_wildcard_present=is_wildcard_present,
            san_count=len(parsed.san_dns_names),
            first_seen_ct=now,
            last_seen_ct=now,
        )
        .on_conflict_do_update(
            index_elements=["fingerprint_sha256"],
            set_={
                "last_seen_ct": now,
                "is_wildcard_present": is_wildcard_present,
                "san_count": len(parsed.san_dns_names),
            },
        )
        .returning(Certificate.id)
    )
    result = await session.execute(stmt)
    row = result.fetchone()
    assert row is not None  # noqa: S101  — RETURNING always yields a row
    return uuid.UUID(str(row[0]))


async def upsert_hostname(
    session: AsyncSession,
    hostname: str,
    certificate: ParsedCertificate,
) -> uuid.UUID:
    """Upsert a ``Hostname`` row and return its ``id``.

    On conflict the ``last_seen_ct`` and latest certificate metadata are updated
    when the certificate's ``not_before`` is newer than what's stored.

    Args:
        session:     Active async database session.
        hostname:    Normalized hostname string (lowercase, no trailing dot).
        certificate: Parsed certificate that contains this hostname.

    Returns:
        The ``id`` of the upserted hostname.
    """
    now = datetime.now(UTC)
    reg_domain = extract_registrable_domain(hostname)
    is_wildcard = hostname.startswith("*.")

    stmt = (
        pg_insert(Hostname)
        .values(
            hostname=hostname,
            registrable_domain=reg_domain,
            is_wildcard=is_wildcard,
            first_seen_ct=now,
            last_seen_ct=now,
            latest_cert_fingerprint_sha256=certificate.fingerprint_sha256,
            latest_cert_not_before=certificate.not_before,
            latest_cert_not_after=certificate.not_after,
        )
        .on_conflict_do_update(
            index_elements=["hostname"],
            set_={
                "last_seen_ct": now,
                "latest_cert_fingerprint_sha256": certificate.fingerprint_sha256,
                "latest_cert_not_before": certificate.not_before,
                "latest_cert_not_after": certificate.not_after,
            },
        )
        .returning(Hostname.id)
    )
    result = await session.execute(stmt)
    row = result.fetchone()
    assert row is not None  # noqa: S101  — RETURNING always yields a row
    return uuid.UUID(str(row[0]))


async def upsert_certificate_hostname(
    session: AsyncSession,
    certificate_id: uuid.UUID,
    hostname_id: uuid.UUID,
) -> None:
    """Ensure the M2M join row between a certificate and hostname exists.

    Silently does nothing when the row already exists (``ON CONFLICT DO NOTHING``).

    Args:
        session:        Active async database session.
        certificate_id: FK to ``certificates.id``.
        hostname_id:    FK to ``hostnames.id``.
    """
    stmt = (
        pg_insert(CertificateHostname)
        .values(certificate_id=certificate_id, hostname_id=hostname_id)
        .on_conflict_do_nothing(
            index_elements=["certificate_id", "hostname_id"],
        )
    )
    await session.execute(stmt)
