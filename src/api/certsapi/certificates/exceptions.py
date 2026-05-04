"""Domain exception for the certificate detail endpoint."""

from __future__ import annotations

from certsapi.exceptions import BitsyApiError


class CertificateNotFoundError(BitsyApiError):
    """Raised when no certificate matches the requested fingerprint."""
