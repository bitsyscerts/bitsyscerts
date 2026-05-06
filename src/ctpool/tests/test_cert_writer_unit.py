"""Unit tests for cert_writer no-op fallback paths (non-integration)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock

from ctpool.cert_writer import upsert_certificate, upsert_hostname
from ctpool.pipeline_schemas import ParsedCertificate


class _ResultOneOrNone:
    def __init__(self, value: object | None) -> None:
        self._value = value

    def scalar_one_or_none(self) -> object | None:
        return self._value


class _ResultOne:
    def __init__(self, value: object) -> None:
        self._value = value

    def scalar_one(self) -> object:
        return self._value


def _parsed() -> ParsedCertificate:
    now = datetime(2024, 1, 1, tzinfo=UTC)
    return ParsedCertificate(
        fingerprint_sha256="a" * 64,
        spki_sha256="b" * 64,
        serial_number="01",
        issuer_dn="CN=Issuer",
        issuer_common_name="Issuer",
        issuer_organization="Org",
        subject_dn="CN=example.com",
        subject_common_name="example.com",
        not_before=now,
        not_after=now,
        signature_algorithm_oid="1.2.840.113549.1.1.11",
        signature_algorithm_name="sha256WithRSAEncryption",
        public_key_algorithm_oid="1.2.840.113549.1.1.1",
        public_key_algorithm_name="rsaEncryption",
        public_key_bits_or_curve="2048",
        is_precertificate=False,
        san_dns_names=["example.com"],
    )


async def test_upsert_certificate_uses_returning_id_when_present() -> None:
    session = AsyncMock()
    expected = uuid.uuid4()
    session.execute = AsyncMock(return_value=_ResultOneOrNone(expected))

    out = await upsert_certificate(session, _parsed(), is_wildcard_present=False)

    assert out == expected
    assert session.execute.await_count == 1


async def test_upsert_certificate_fallback_selects_existing_id() -> None:
    session = AsyncMock()
    expected = uuid.uuid4()
    session.execute = AsyncMock(
        side_effect=[
            _ResultOneOrNone(None),
            _ResultOne(expected),
        ]
    )

    out = await upsert_certificate(session, _parsed(), is_wildcard_present=False)

    assert out == expected
    assert session.execute.await_count == 2


async def test_upsert_hostname_uses_returning_id_when_present() -> None:
    session = AsyncMock()
    expected = uuid.uuid4()
    session.execute = AsyncMock(return_value=_ResultOneOrNone(expected))

    out = await upsert_hostname(session, "example.com", _parsed())

    assert out == expected
    assert session.execute.await_count == 1


async def test_upsert_hostname_fallback_selects_existing_id() -> None:
    session = AsyncMock()
    expected = uuid.uuid4()
    session.execute = AsyncMock(
        side_effect=[
            _ResultOneOrNone(None),
            _ResultOne(expected),
        ]
    )

    out = await upsert_hostname(session, "example.com", _parsed())

    assert out == expected
    assert session.execute.await_count == 2
