"""Tests for CertificateService — mocked repository."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from certsapi.certificates.exceptions import CertificateNotFoundError
from certsapi.certificates.models import CertificateResponse
from certsapi.certificates.service import CertificateService


def _make_response(fp: str = "abc123") -> CertificateResponse:
    now = datetime.now(UTC)
    return CertificateResponse(
        id=uuid.uuid4(),
        fingerprint_sha256=fp,
        spki_sha256=fp,
        serial_number="01",
        issuer_dn="CN=CA",
        issuer_common_name=None,
        issuer_organization=None,
        subject_dn="CN=test",
        subject_common_name=None,
        not_before=now,
        not_after=now,
        signature_algorithm_oid="1.2",
        signature_algorithm_name="sha256",
        public_key_algorithm_oid="1.2",
        public_key_algorithm_name="rsa",
        public_key_bits_or_curve=None,
        is_precertificate=False,
        is_wildcard_present=False,
        san_count=1,
        first_seen_ct=None,
        last_seen_ct=None,
        subject_alternative_names=["api.example.com"],
    )


class TestCertificateService:
    async def test_found_returns_certificate_response(self) -> None:
        repo = AsyncMock()
        repo.get_by_fingerprint.return_value = _make_response("abc")
        service = CertificateService(repo)

        result = await service.get_by_fingerprint("abc")

        assert result.fingerprint_sha256 == "abc"

    async def test_not_found_raises_certificate_not_found_error(self) -> None:
        repo = AsyncMock()
        repo.get_by_fingerprint.return_value = None
        service = CertificateService(repo)

        with pytest.raises(CertificateNotFoundError):
            await service.get_by_fingerprint("missing")
