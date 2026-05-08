"""Root index router: GET / returns a JSON map of all API endpoints."""

from __future__ import annotations

from fastapi import APIRouter

from certsapi.config import get_settings
from certsapi.root.models import EndpointEntry, RootResponse

root_router = APIRouter(tags=["root"])

_ENDPOINTS: list[EndpointEntry] = [
    EndpointEntry(
        path="/v1/hostnames",
        method="GET",
        description="Search CT-observed hostnames (local index) with cursor pagination",
    ),
    EndpointEntry(
        path="/v1/certificates/{fingerprint_sha256}",
        method="GET",
        description="Retrieve a CT-observed certificate by its SHA-256 fingerprint",
    ),
    EndpointEntry(
        path="/health",
        method="GET",
        description="Liveness probe — always HTTP 200",
    ),
    EndpointEntry(
        path="/v1/stats",
        method="GET",
        description="Global and per-log ingestion statistics",
    ),
]


@root_router.get(
    "/",
    response_model=RootResponse,
    summary="API index",
)
async def index() -> RootResponse:
    """Return a JSON index of all available endpoints and documentation links."""
    settings = get_settings()
    return RootResponse(
        service=settings.app_name,
        version=settings.app_version,
        docs="/docs",
        openapi="/openapi.json",
        endpoints=_ENDPOINTS,
    )
