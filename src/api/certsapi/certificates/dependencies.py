"""FastAPI Depends() factories for the certificates domain."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from certsapi.certificates.repository import CertificateRepository
from certsapi.certificates.service import CertificateService
from certsapi.database import get_db


def get_certificate_repository(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> CertificateRepository:
    """Instantiate a CertificateRepository bound to the request-scoped session."""
    return CertificateRepository(session)


def get_certificate_service(
    repo: Annotated[CertificateRepository, Depends(get_certificate_repository)],
) -> CertificateService:
    """Instantiate a CertificateService with an injected repository."""
    return CertificateService(repo)
