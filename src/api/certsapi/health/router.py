"""Health check router: GET /health."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from certsapi.database import get_db
from certsapi.health.models import HealthResponse
from certsapi.health.service import HealthService

health_router = APIRouter(tags=["health"])


def _get_health_service(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> HealthService:
    """Instantiate a HealthService bound to the request-scoped session."""
    return HealthService(session)


@health_router.get(
    "/health",
    response_model=HealthResponse,
    summary="Liveness probe",
)
async def health_check(
    service: Annotated[HealthService, Depends(_get_health_service)],
) -> HealthResponse:
    """Return HTTP 200 always; db field indicates database reachability.

    Safe for load-balancer health probes — never returns 5xx.
    """
    return await service.check()
