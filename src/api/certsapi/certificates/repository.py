"""Certificate database queries: fetch one cert by fingerprint with hostnames."""

from __future__ import annotations

import uuid

from ctpool.models.certificate import Certificate
from ctpool.models.certificate_hostname import CertificateHostname
from ctpool.models.hostname import Hostname
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from certsapi.certificates.models import CertificateResponse


def _to_response(cert: Certificate, hostnames: list[str]) -> CertificateResponse:
    """Convert a Certificate ORM row + hostname list to a CertificateResponse."""
    return CertificateResponse(
        id=cert.id,
        fingerprint_sha256=cert.fingerprint_sha256,
        spki_sha256=cert.spki_sha256,
        serial_number=cert.serial_number,
        issuer_dn=cert.issuer_dn,
        issuer_common_name=cert.issuer_common_name,
        issuer_organization=cert.issuer_organization,
        subject_dn=cert.subject_dn,
        subject_common_name=cert.subject_common_name,
        not_before=cert.not_before,
        not_after=cert.not_after,
        signature_algorithm_oid=cert.signature_algorithm_oid,
        signature_algorithm_name=cert.signature_algorithm_name,
        public_key_algorithm_oid=cert.public_key_algorithm_oid,
        public_key_algorithm_name=cert.public_key_algorithm_name,
        public_key_bits_or_curve=cert.public_key_bits_or_curve,
        is_precertificate=cert.is_precertificate,
        is_wildcard_present=cert.is_wildcard_present,
        san_count=cert.san_count,
        first_seen_ct=cert.first_seen_ct,
        last_seen_ct=cert.last_seen_ct,
        subject_alternative_names=hostnames,
    )


class CertificateRepository:
    """Fetches one certificate by fingerprint with its associated hostnames."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_fingerprint(self, fingerprint: str) -> CertificateResponse | None:
        """Return a CertificateResponse or None when fingerprint is not found."""
        stmt = select(Certificate).where(Certificate.fingerprint_sha256 == fingerprint)
        cert = (await self._session.execute(stmt)).scalar_one_or_none()
        if cert is None:
            return None
        hostnames = await self._get_hostnames(cert.id)
        return _to_response(cert, hostnames)

    async def _get_hostnames(self, cert_id: uuid.UUID) -> list[str]:
        """Return sorted hostnames associated with the given certificate ID."""
        stmt = (
            select(Hostname.hostname)
            .join(
                CertificateHostname,
                CertificateHostname.hostname_id == Hostname.id,
            )
            .where(CertificateHostname.certificate_id == cert_id)
            .order_by(Hostname.hostname)
        )
        return list((await self._session.execute(stmt)).scalars().all())
