"""FastAPI Depends() factories for the hostnames domain."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from certsapi.database import get_db
from certsapi.hostnames.models import HostnameSearchParams, SortField
from certsapi.hostnames.repository import HostnameRepository
from certsapi.hostnames.service import HostnameService


async def get_hostname_params(
    q: str = Query(..., description="Hostname query: exact, *.prefix, re:pattern"),  # noqa: B008
    recursive: bool = Query(default=False, description="Search by registrable domain"),  # noqa: B008
    depth: int | None = Query(default=None, ge=0, description="Sub-label depth limit"),  # noqa: B008
    sort: SortField = Query(  # noqa: B008
        default=SortField.not_before_desc, description="Sort order"
    ),
    limit: int = Query(default=50, ge=1, le=200, description="Max results"),  # noqa: B008
    cursor: str | None = Query(default=None, description="Pagination cursor"),  # noqa: B008
    include_certs: bool = Query(default=False, description="Embed latest cert data"),  # noqa: B008
) -> HostnameSearchParams:
    """Parse and validate hostname search query parameters."""
    return HostnameSearchParams(
        q=q,
        recursive=recursive,
        depth=depth,
        sort=sort,
        limit=limit,
        cursor=cursor,
        include_certs=include_certs,
    )


def get_hostname_repository(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> HostnameRepository:
    """Instantiate a HostnameRepository bound to the request-scoped session."""
    return HostnameRepository(session)


def get_hostname_service(
    repo: Annotated[HostnameRepository, Depends(get_hostname_repository)],
) -> HostnameService:
    """Instantiate a HostnameService with an injected repository."""
    return HostnameService(repo)
