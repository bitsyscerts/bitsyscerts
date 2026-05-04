"""Certificate service: retrieves a certificate by fingerprint or raises."""

from __future__ import annotations

from certsapi.certificates.exceptions import CertificateNotFoundError
from certsapi.certificates.models import CertificateResponse
from certsapi.certificates.repository import CertificateRepository


class CertificateService:
    """Calls the repository and raises CertificateNotFoundError on a miss."""

    def __init__(self, repository: CertificateRepository) -> None:
        self._repository = repository

    async def get_by_fingerprint(self, fingerprint: str) -> CertificateResponse:
        """Return the certificate matching *fingerprint*.

        Raises:
            CertificateNotFoundError: If no certificate has that fingerprint.
        """
        result = await self._repository.get_by_fingerprint(fingerprint)
        if result is None:
            raise CertificateNotFoundError(f"Certificate not found: {fingerprint}")
        return result
