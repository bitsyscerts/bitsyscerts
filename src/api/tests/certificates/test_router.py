"""HTTP-level tests for GET /v1/certificates/{fingerprint_sha256}."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock

from httpx import ASGITransport, AsyncClient

from certsapi.app import create_app
from certsapi.certificates.dependencies import get_certificate_service
from certsapi.certificates.exceptions import CertificateNotFoundError
from certsapi.certificates.models import CertificateResponse
from certsapi.config import Settings

_UNIT_TEST_SETTINGS = Settings.model_validate(
    {"database_url": "postgresql+psycopg://localhost/test"}
)


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


def _client_with_service(service: object) -> AsyncClient:
    app = create_app(settings=_UNIT_TEST_SETTINGS)
    app.dependency_overrides[get_certificate_service] = lambda: service  # type: ignore[attr-defined]
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


class TestCertificateRouter:
    async def test_found_returns_200_with_all_fields(self) -> None:
        fp = "abc123"
        svc = AsyncMock()
        svc.get_by_fingerprint.return_value = _make_response(fp)
        async with _client_with_service(svc) as client:
            resp = await client.get(f"/v1/certificates/{fp}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["fingerprint_sha256"] == fp
        assert "subject_alternative_names" in body
        assert isinstance(body["subject_alternative_names"], list)

    async def test_not_found_returns_404(self) -> None:
        svc = AsyncMock()
        svc.get_by_fingerprint.side_effect = CertificateNotFoundError("not found")
        async with _client_with_service(svc) as client:
            resp = await client.get("/v1/certificates/deadbeef")
        assert resp.status_code == 404

    async def test_response_contains_required_cert_fields(self) -> None:
        svc = AsyncMock()
        svc.get_by_fingerprint.return_value = _make_response()
        async with _client_with_service(svc) as client:
            resp = await client.get("/v1/certificates/abc123")
        body = resp.json()
        for field in (
            "id",
            "fingerprint_sha256",
            "spki_sha256",
            "serial_number",
            "issuer_dn",
            "subject_dn",
            "not_before",
            "not_after",
            "is_precertificate",
            "is_wildcard_present",
            "san_count",
        ):
            assert field in body, f"Missing field: {field}"
