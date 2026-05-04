"""Hostname search router: GET /v1/hostnames."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from certsapi.hostnames.dependencies import get_hostname_params, get_hostname_service
from certsapi.hostnames.models import HostnameListResponse, HostnameSearchParams
from certsapi.hostnames.service import HostnameService

hostname_router = APIRouter(tags=["hostnames"])


@hostname_router.get(
    "/v1/hostnames",
    response_model=HostnameListResponse,
    summary="Search CT-observed hostnames",
)
async def search_hostnames(
    params: Annotated[HostnameSearchParams, Depends(get_hostname_params)],
    service: Annotated[HostnameService, Depends(get_hostname_service)],
) -> HostnameListResponse:
    """Search hostnames observed in Certificate Transparency logs.

    Supports exact match, wildcard (`*.example.com`), regex (`re:pattern`),
    and registrable-domain search (`recursive=true`). Results are
    cursor-paginated using keyset pagination on certificate timestamps.
    """
    return await service.search(params)
