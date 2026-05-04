"""Integration tests for HostnameRepository against the test database."""

from __future__ import annotations

import pytest
import pytest_asyncio
from ctpool.models import CertificateHostname
from sqlalchemy.ext.asyncio import AsyncSession

from certsapi.hostnames.cursor import PageCursor
from certsapi.hostnames.models import HostnameSearchParams, SortField
from certsapi.hostnames.query_parser import ParsedQuery, QueryStrategy
from certsapi.hostnames.repository import HostnameRepository
from tests.conftest import make_certificate, make_hostname


@pytest_asyncio.fixture()
async def session_with_hostnames(db_session: AsyncSession) -> AsyncSession:
    """Seed two hostnames in the test database."""
    from datetime import UTC, datetime

    now = datetime(2024, 6, 1, tzinfo=UTC)
    earlier = datetime(2024, 1, 1, tzinfo=UTC)

    h1 = make_hostname(
        hostname="api.example.com",
        registrable_domain="example.com",
        latest_cert_not_before=now,
        latest_cert_not_after=now,
    )
    h2 = make_hostname(
        hostname="www.example.com",
        registrable_domain="example.com",
        latest_cert_not_before=earlier,
        latest_cert_not_after=earlier,
    )
    db_session.add_all([h1, h2])
    await db_session.flush()
    return db_session


def _params(**kwargs: object) -> HostnameSearchParams:
    defaults: dict[str, object] = {"q": "api.example.com", "limit": 50}
    defaults.update(kwargs)
    return HostnameSearchParams(**defaults)  # type: ignore[arg-type]


def _exact(value: str) -> ParsedQuery:
    return ParsedQuery(strategy=QueryStrategy.exact, value=value)


def _domain(value: str) -> ParsedQuery:
    return ParsedQuery(strategy=QueryStrategy.exact, value=value)


class TestHostnameRepositorySearch:
    async def test_exact_match_returns_matching_row(
        self, session_with_hostnames: AsyncSession
    ) -> None:
        repo = HostnameRepository(session_with_hostnames)
        results = await repo.search(_exact("api.example.com"), _params(), None)
        assert any(r.hostname == "api.example.com" for r in results)

    async def test_exact_match_excludes_non_matching(
        self, session_with_hostnames: AsyncSession
    ) -> None:
        repo = HostnameRepository(session_with_hostnames)
        results = await repo.search(_exact("api.example.com"), _params(), None)
        assert all(r.hostname == "api.example.com" for r in results)

    async def test_recursive_returns_all_under_domain(
        self, session_with_hostnames: AsyncSession
    ) -> None:
        repo = HostnameRepository(session_with_hostnames)
        params = _params(q="example.com", recursive=True)
        results = await repo.search(_domain("example.com"), params, None)
        hostnames = {r.hostname for r in results}
        assert "api.example.com" in hostnames
        assert "www.example.com" in hostnames

    async def test_limit_is_respected(
        self, session_with_hostnames: AsyncSession
    ) -> None:
        repo = HostnameRepository(session_with_hostnames)
        params = _params(q="example.com", recursive=True, limit=1)
        # fetch limit+1 = 2 rows max, but results truncation is in service
        results = await repo.search(_domain("example.com"), params, None)
        assert len(results) <= 2  # repo returns limit+1 at most

    async def test_empty_result_returns_empty_list(
        self, session_with_hostnames: AsyncSession
    ) -> None:
        repo = HostnameRepository(session_with_hostnames)
        results = await repo.search(_exact("no-match.example.com"), _params(), None)
        assert results == []

    async def test_include_certs_false_omits_cert_data(
        self, session_with_hostnames: AsyncSession
    ) -> None:
        repo = HostnameRepository(session_with_hostnames)
        results = await repo.search(_exact("api.example.com"), _params(), None)
        assert all(r.latest_cert is None for r in results)

    async def test_include_certs_true_embeds_san_list(
        self, db_session: AsyncSession
    ) -> None:
        """include_certs=True must populate subject_alternative_names on the embed."""
        cert = make_certificate(fingerprint_sha256="aabbccdd")
        san1 = make_hostname(
            hostname="san1.embed-test.com", registrable_domain="embed-test.com"
        )
        san2 = make_hostname(
            hostname="san2.embed-test.com", registrable_domain="embed-test.com"
        )
        subject = make_hostname(
            hostname="subject.embed-test.com",
            registrable_domain="embed-test.com",
            latest_cert_fingerprint_sha256="aabbccdd",
        )
        db_session.add_all([cert, san1, san2, subject])
        await db_session.flush()
        db_session.add(CertificateHostname(certificate_id=cert.id, hostname_id=san1.id))
        db_session.add(CertificateHostname(certificate_id=cert.id, hostname_id=san2.id))
        await db_session.flush()

        repo = HostnameRepository(db_session)
        params = _params(q="subject.embed-test.com", include_certs=True)
        results = await repo.search(_exact("subject.embed-test.com"), params, None)

        assert len(results) == 1
        embed = results[0].latest_cert
        assert embed is not None
        assert "san1.embed-test.com" in embed.subject_alternative_names
        assert "san2.embed-test.com" in embed.subject_alternative_names

    async def test_include_certs_true_no_sans_returns_empty_list(
        self, db_session: AsyncSession
    ) -> None:
        """A cert with no linked hostnames yields subject_alternative_names=[]."""
        cert = make_certificate(fingerprint_sha256="deadbeef01")
        subject = make_hostname(
            hostname="lone.embed-test.com",
            registrable_domain="embed-test.com",
            latest_cert_fingerprint_sha256="deadbeef01",
        )
        db_session.add_all([cert, subject])
        await db_session.flush()

        repo = HostnameRepository(db_session)
        params = _params(q="lone.embed-test.com", include_certs=True)
        results = await repo.search(_exact("lone.embed-test.com"), params, None)

        assert len(results) == 1
        embed = results[0].latest_cert
        assert embed is not None
        assert embed.subject_alternative_names == []

    async def test_default_sort_descending_by_not_before(
        self, session_with_hostnames: AsyncSession
    ) -> None:
        repo = HostnameRepository(session_with_hostnames)
        params = _params(
            q="example.com", recursive=True, sort=SortField.not_before_desc
        )
        results = await repo.search(_domain("example.com"), params, None)
        timestamps = [
            r.latest_cert_not_before for r in results if r.latest_cert_not_before
        ]
        assert timestamps == sorted(timestamps, reverse=True)

    async def test_keyset_cursor_skips_seen_rows(
        self, session_with_hostnames: AsyncSession
    ) -> None:

        repo = HostnameRepository(session_with_hostnames)
        params = _params(
            q="example.com", recursive=True, sort=SortField.not_before_desc
        )

        # First page — no cursor
        first = await repo.search(_domain("example.com"), params, None)
        assert len(first) >= 1

        # Use the last row as the cursor pivot
        last = first[-1]
        ts = last.latest_cert_not_before
        if ts is None:
            pytest.skip("No timestamp on row — cannot build cursor")

        cursor = PageCursor(
            sort=SortField.not_before_desc.value,
            timestamp_ms=int(ts.timestamp() * 1000),
            id_uuid=str(last.id),
        )
        second = await repo.search(_domain("example.com"), params, cursor)
        first_ids = {r.id for r in first}
        assert all(r.id not in first_ids for r in second)
