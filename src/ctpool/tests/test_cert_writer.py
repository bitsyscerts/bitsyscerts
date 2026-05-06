"""Tests for ctpool.cert_writer — upsert_certificate, upsert_hostname, and
upsert_certificate_hostname.

All tests use the real ``ctpool_test`` database via the ``db_session`` fixture;
every test is automatically rolled back.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ctpool.cert_writer import (
    upsert_certificate,
    upsert_certificate_hostname,
    upsert_hostname,
)
from ctpool.models.certificate import Certificate
from ctpool.models.certificate_hostname import CertificateHostname
from ctpool.models.hostname import Hostname
from ctpool.pipeline_schemas import ParsedCertificate

pytestmark = pytest.mark.integration

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_NOW = datetime(2024, 1, 1, 0, 0, 0, tzinfo=UTC)


def _make_parsed(
    *,
    fingerprint: str = "a" * 64,
    san_dns_names: list[str] | None = None,
) -> ParsedCertificate:
    return ParsedCertificate(
        fingerprint_sha256=fingerprint,
        spki_sha256="b" * 64,
        serial_number="0102",
        issuer_dn="CN=Test CA",
        issuer_common_name="Test CA",
        issuer_organization="Test Org",
        subject_dn="CN=example.com",
        subject_common_name="example.com",
        not_before=_NOW,
        not_after=_NOW,
        signature_algorithm_oid="1.2.840.113549.1.1.11",
        signature_algorithm_name="sha256WithRSAEncryption",
        public_key_algorithm_oid="1.2.840.113549.1.1.1",
        public_key_algorithm_name="rsaEncryption",
        public_key_bits_or_curve="2048",
        is_precertificate=False,
        san_dns_names=san_dns_names or ["example.com"],
    )


# ---------------------------------------------------------------------------
# upsert_certificate
# ---------------------------------------------------------------------------


async def test_upsert_certificate_inserts_row(db_session: AsyncSession) -> None:
    """First call inserts a certificate and returns a valid UUID."""
    parsed = _make_parsed()
    cert_id = await upsert_certificate(db_session, parsed, is_wildcard_present=False)

    assert isinstance(cert_id, uuid.UUID)
    row = await db_session.get(Certificate, cert_id)
    assert row is not None
    assert row.fingerprint_sha256 == parsed.fingerprint_sha256


async def test_upsert_certificate_idempotent(db_session: AsyncSession) -> None:
    """Second call with same fingerprint returns the same UUID."""
    parsed = _make_parsed()
    id1 = await upsert_certificate(db_session, parsed, is_wildcard_present=False)
    id2 = await upsert_certificate(db_session, parsed, is_wildcard_present=True)

    assert id1 == id2


async def test_upsert_certificate_idempotent_noop_conflict(
    db_session: AsyncSession,
) -> None:
    """No-op conflict path still returns existing certificate UUID."""
    parsed = _make_parsed()
    id1 = await upsert_certificate(db_session, parsed, is_wildcard_present=False)
    id2 = await upsert_certificate(db_session, parsed, is_wildcard_present=False)

    assert id1 == id2


async def test_upsert_certificate_updates_on_conflict(db_session: AsyncSession) -> None:
    """On conflict, wildcard flag and san_count are updated."""
    parsed = _make_parsed(san_dns_names=["example.com"])
    cert_id = await upsert_certificate(db_session, parsed, is_wildcard_present=False)

    parsed2 = _make_parsed(san_dns_names=["example.com", "www.example.com"])
    await upsert_certificate(db_session, parsed2, is_wildcard_present=True)

    await db_session.refresh(await db_session.get(Certificate, cert_id))  # noqa: E501
    row = await db_session.get(Certificate, cert_id)
    assert row is not None
    assert row.is_wildcard_present is True
    assert row.san_count == 2


# ---------------------------------------------------------------------------
# upsert_hostname
# ---------------------------------------------------------------------------


async def test_upsert_hostname_inserts_row(db_session: AsyncSession) -> None:
    """First call inserts a hostname and returns a valid UUID."""
    parsed = _make_parsed()
    h_id = await upsert_hostname(db_session, "example.com", parsed)

    assert isinstance(h_id, uuid.UUID)
    row = await db_session.get(Hostname, h_id)
    assert row is not None
    assert row.hostname == "example.com"


async def test_upsert_hostname_idempotent(db_session: AsyncSession) -> None:
    """Second call with same hostname returns the same UUID."""
    parsed = _make_parsed()
    id1 = await upsert_hostname(db_session, "example.com", parsed)
    id2 = await upsert_hostname(db_session, "example.com", parsed)
    assert id1 == id2


async def test_upsert_hostname_wildcard_detected(db_session: AsyncSession) -> None:
    """Wildcard hostname sets is_wildcard=True."""
    parsed = _make_parsed()
    h_id = await upsert_hostname(db_session, "*.example.com", parsed)
    row = await db_session.get(Hostname, h_id)
    assert row is not None
    assert row.is_wildcard is True


async def test_upsert_hostname_non_wildcard(db_session: AsyncSession) -> None:
    """Non-wildcard hostname sets is_wildcard=False."""
    parsed = _make_parsed()
    h_id = await upsert_hostname(db_session, "example.com", parsed)
    row = await db_session.get(Hostname, h_id)
    assert row is not None
    assert row.is_wildcard is False


async def test_upsert_hostname_registrable_domain(db_session: AsyncSession) -> None:
    """Registrable domain is extracted correctly."""
    parsed = _make_parsed()
    h_id = await upsert_hostname(db_session, "sub.example.com", parsed)
    row = await db_session.get(Hostname, h_id)
    assert row is not None
    assert row.registrable_domain == "example.com"


# ---------------------------------------------------------------------------
# upsert_certificate_hostname
# ---------------------------------------------------------------------------


async def test_upsert_certificate_hostname_inserts_join_row(
    db_session: AsyncSession,
) -> None:
    """Join row is created between a certificate and hostname."""
    parsed = _make_parsed()
    cert_id = await upsert_certificate(db_session, parsed, is_wildcard_present=False)
    h_id = await upsert_hostname(db_session, "example.com", parsed)

    await upsert_certificate_hostname(db_session, cert_id, h_id)

    result = await db_session.execute(
        select(CertificateHostname).where(
            CertificateHostname.certificate_id == cert_id,
            CertificateHostname.hostname_id == h_id,
        )
    )
    assert result.scalars().first() is not None


async def test_upsert_certificate_hostname_idempotent(db_session: AsyncSession) -> None:
    """Inserting the same join row twice does not raise an error."""
    parsed = _make_parsed()
    cert_id = await upsert_certificate(db_session, parsed, is_wildcard_present=False)
    h_id = await upsert_hostname(db_session, "example.com", parsed)

    await upsert_certificate_hostname(db_session, cert_id, h_id)
    await upsert_certificate_hostname(db_session, cert_id, h_id)  # must not raise
