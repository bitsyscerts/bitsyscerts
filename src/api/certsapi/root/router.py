"""Root index router: GET / returns a JSON map of all API endpoints."""

from __future__ import annotations

from typing import cast

from fastapi import APIRouter, Request

from certsapi.config import Settings
from certsapi.root.models import EndpointEntry, RootResponse

root_router = APIRouter(tags=["root"])

_BASE_ENDPOINTS: list[EndpointEntry] = [
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
]

_STATS_ENDPOINT = EndpointEntry(
    path="/v1/stats",
    method="GET",
    description="Global and per-log ingestion statistics",
)


def _get_app_settings(request: Request) -> Settings:
    """Return the Settings instance attached by the application factory."""
    return cast(Settings, request.app.state.settings)


def _build_endpoint_inventory(settings: Settings) -> list[EndpointEntry]:
    """Return the root endpoint list for the current exposure settings."""
    endpoints = list(_BASE_ENDPOINTS)
    if settings.expose_stats_api:
        endpoints.append(_STATS_ENDPOINT)
    return endpoints


@root_router.get(
    "/",
    response_model=RootResponse,
    summary="API index",
)
async def index(request: Request) -> RootResponse:
    """Return a JSON index of all available endpoints and documentation links."""
    settings = _get_app_settings(request)
    return RootResponse(
        service=settings.app_name,
        version=settings.app_version,
        docs="/docs",
        openapi="/openapi.json",
        endpoints=_build_endpoint_inventory(settings),
    )
