"""Upsert Certificate, Hostname, and CertificateHostname rows idempotently.

Exports:
    upsert_certificate         — Upsert a certificate row; return its id.
    upsert_hostname            — Upsert a hostname row; return its id.
    upsert_certificate_hostname — Ensure the M2M join row exists.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from ctpool.entry_write_result import CertificateUpsertResult, HostnameUpsertResult
from ctpool.hostname_latest_cert import (
    IncomingCertSummary,
    StoredCertSummary,
    build_latest_cert_fields,
    should_update_latest_cert,
)
from ctpool.models.certificate import Certificate
from ctpool.models.certificate_hostname import CertificateHostname
from ctpool.models.hostname import Hostname
from ctpool.normalizer import extract_registrable_domain
from ctpool.pipeline_schemas import ParsedCertificate


async def upsert_certificate(
    session: AsyncSession,
    parsed: ParsedCertificate,
    is_wildcard_present: bool,
) -> CertificateUpsertResult:
    """Upsert a ``Certificate`` row and return its ``id``.

    On conflict (``fingerprint_sha256`` already exists) the function returns
    the existing row id and marks the write as a duplicate.  Metadata updates
    remain local to this function so callers never need a follow-up query.

    Args:
        session:            Active async database session.
        parsed:             Validated certificate data from the parser.
        is_wildcard_present: True if any SAN contains a wildcard.

    Returns:
        Typed result with the ``Certificate`` id and insertion classification.
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
        .on_conflict_do_nothing(
            index_elements=["fingerprint_sha256"],
        )
        .returning(Certificate.id)
    )
    result = await session.execute(stmt)
    inserted_id = result.scalar_one_or_none()
    if inserted_id is not None:
        return CertificateUpsertResult(
            certificate_id=uuid.UUID(str(inserted_id)),
            inserted=True,
        )

    existing_result = await session.execute(
        select(
            Certificate.id,
            Certificate.is_wildcard_present,
            Certificate.san_count,
        ).where(Certificate.fingerprint_sha256 == parsed.fingerprint_sha256)
    )
    existing_row = existing_result.one()
    certificate_id = uuid.UUID(str(existing_row[0]))
    san_count = len(parsed.san_dns_names)
    if existing_row[1] != is_wildcard_present or existing_row[2] != san_count:
        await session.execute(
            update(Certificate)
            .where(Certificate.id == certificate_id)
            .values(
                last_seen_ct=now,
                is_wildcard_present=is_wildcard_present,
                san_count=san_count,
            )
        )
    return CertificateUpsertResult(certificate_id=certificate_id, inserted=False)


async def upsert_hostname(
    session: AsyncSession,
    hostname: str,
    certificate: ParsedCertificate,
    *,
    observed_at: datetime,
) -> HostnameUpsertResult:
    """Upsert a ``Hostname`` row and return its ``id``.

    Uses a two-step SELECT + Python ranking approach so that all five
    deterministic ranking rules are applied without a complex SQL expression.
    The hostname is first inserted/touched (updating ``last_seen_ct`` only),
    then the stored cert summary is compared against the incoming cert.  If
    the incoming cert wins the ranking, all ten ``latest_cert_*`` fields are
    updated in a second statement.

    Args:
        session:     Active async database session.
        hostname:    Normalized hostname string (lowercase, no trailing dot).
        certificate: Parsed certificate that contains this hostname.
        observed_at: Timestamp at which this entry was processed.

    Returns:
        Typed result with the ``Hostname`` id and insertion classification.
    """
    reg_domain = extract_registrable_domain(hostname)
    is_wildcard = hostname.startswith("*.")

    insert_stmt = (
        pg_insert(Hostname)
        .values(
            hostname=hostname,
            registrable_domain=reg_domain,
            is_wildcard=is_wildcard,
            first_seen_ct=observed_at,
            last_seen_ct=observed_at,
        )
        .on_conflict_do_nothing(index_elements=["hostname"])
        .returning(
            Hostname.id,
            Hostname.latest_cert_fingerprint_sha256,
            Hostname.latest_cert_not_before,
            Hostname.latest_cert_not_after,
            Hostname.latest_cert_seen_at,
        )
    )
    insert_result = await session.execute(insert_stmt)
    inserted_row = insert_result.one_or_none()
    inserted = inserted_row is not None
    if inserted_row is None:
        update_result = await session.execute(
            update(Hostname)
            .where(Hostname.hostname == hostname)
            .values(last_seen_ct=observed_at)
            .returning(
                Hostname.id,
                Hostname.latest_cert_fingerprint_sha256,
                Hostname.latest_cert_not_before,
                Hostname.latest_cert_not_after,
                Hostname.latest_cert_seen_at,
            )
        )
        row = update_result.one()
    else:
        row = inserted_row
    hostname_id = uuid.UUID(str(row[0]))

    # Step 2: apply ranking and conditionally update the latest-cert summary.
    stored = StoredCertSummary(
        fingerprint_sha256=row[1],
        not_before=row[2],
        not_after=row[3],
        seen_at=row[4],
    )
    incoming = IncomingCertSummary(
        fingerprint_sha256=certificate.fingerprint_sha256,
        not_before=certificate.not_before,
        not_after=certificate.not_after,
        issuer_cn=certificate.issuer_common_name,
        issuer_org=certificate.issuer_organization,
        subject_cn=certificate.subject_common_name,
        is_precert=certificate.is_precertificate,
        observed_at=observed_at,
    )
    if should_update_latest_cert(stored, incoming):
        fields = build_latest_cert_fields(incoming)
        await session.execute(
            update(Hostname).where(Hostname.id == hostname_id).values(**fields)
        )

    return HostnameUpsertResult(hostname_id=hostname_id, inserted=inserted)


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
