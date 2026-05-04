"""Certificate detail router: GET /v1/certificates/{fingerprint_sha256}."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from certsapi.certificates.dependencies import get_certificate_service
from certsapi.certificates.models import CertificateResponse
from certsapi.certificates.service import CertificateService

certificate_router = APIRouter(tags=["certificates"])


@certificate_router.get(
    "/v1/certificates/{fingerprint_sha256}",
    response_model=CertificateResponse,
    summary="Get certificate by SHA-256 fingerprint",
)
async def get_certificate(
    fingerprint_sha256: str,
    service: Annotated[CertificateService, Depends(get_certificate_service)],
) -> CertificateResponse:
    """Retrieve a single X.509 certificate by its SHA-256 fingerprint.

    Returns all certificate fields plus the list of hostnames linked to
    this certificate via the certificate_hostnames join table.
    """
    return await service.get_by_fingerprint(fingerprint_sha256)
