"""Integration tests for CertificateRepository against the test database."""

from __future__ import annotations

import pytest_asyncio
from ctpool.models import CertificateHostname
from sqlalchemy.ext.asyncio import AsyncSession

from certsapi.certificates.repository import CertificateRepository
from tests.conftest import make_certificate, make_hostname


@pytest_asyncio.fixture()
async def session_with_cert(db_session: AsyncSession) -> tuple[AsyncSession, str]:
    """Seed one certificate with two linked hostnames, return session + fingerprint."""
    cert = make_certificate()
    h1 = make_hostname(hostname="a.example.com")
    h2 = make_hostname(hostname="b.example.com")
    db_session.add_all([cert, h1, h2])
    await db_session.flush()

    db_session.add(CertificateHostname(certificate_id=cert.id, hostname_id=h1.id))
    db_session.add(CertificateHostname(certificate_id=cert.id, hostname_id=h2.id))
    await db_session.flush()
    return db_session, cert.fingerprint_sha256


class TestCertificateRepository:
    async def test_found_fingerprint_returns_response(
        self, session_with_cert: tuple[AsyncSession, str]
    ) -> None:
        session, fp = session_with_cert
        repo = CertificateRepository(session)
        result = await repo.get_by_fingerprint(fp)
        assert result is not None
        assert result.fingerprint_sha256 == fp

    async def test_response_includes_linked_hostnames(
        self, session_with_cert: tuple[AsyncSession, str]
    ) -> None:
        session, fp = session_with_cert
        repo = CertificateRepository(session)
        result = await repo.get_by_fingerprint(fp)
        assert result is not None
        assert "a.example.com" in result.subject_alternative_names
        assert "b.example.com" in result.subject_alternative_names

    async def test_hostnames_are_sorted(
        self, session_with_cert: tuple[AsyncSession, str]
    ) -> None:
        session, fp = session_with_cert
        repo = CertificateRepository(session)
        result = await repo.get_by_fingerprint(fp)
        assert result is not None
        assert result.subject_alternative_names == sorted(
            result.subject_alternative_names
        )

    async def test_unknown_fingerprint_returns_none(
        self, db_session: AsyncSession
    ) -> None:
        repo = CertificateRepository(db_session)
        result = await repo.get_by_fingerprint("deadbeef" * 8)
        assert result is None

    async def test_no_hostnames_returns_empty_list(
        self, db_session: AsyncSession
    ) -> None:
        cert = make_certificate()
        db_session.add(cert)
        await db_session.flush()
        repo = CertificateRepository(db_session)
        result = await repo.get_by_fingerprint(cert.fingerprint_sha256)
        assert result is not None
        assert result.subject_alternative_names == []
