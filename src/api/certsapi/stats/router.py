"""Stats router: GET /v1/stats."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from certsapi.config import get_settings
from certsapi.database import get_db
from certsapi.stats.models import StatsResponse
from certsapi.stats.repository import StatsRepository
from certsapi.stats.service import StatsService

stats_router = APIRouter(tags=["stats"])


def _get_stats_repository(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> StatsRepository:
    """Instantiate a StatsRepository bound to the request-scoped session."""
    return StatsRepository(session)


def _get_stats_service(
    repo: Annotated[StatsRepository, Depends(_get_stats_repository)],
    request: Request,
) -> StatsService:
    """Instantiate a StatsService with an injected repository."""
    app_settings = getattr(request.app.state, "settings", None)
    stats_stale_seconds = (
        app_settings.stats_stale_seconds
        if app_settings is not None
        else get_settings().stats_stale_seconds
    )
    return StatsService(repo, stats_stale_seconds=stats_stale_seconds)


@stats_router.get(
    "/v1/stats",
    response_model=StatsResponse,
    summary="Ingestion statistics",
)
async def get_stats(
    service: Annotated[StatsService, Depends(_get_stats_service)],
) -> StatsResponse:
    """Return global and per-log ingestion statistics.

    Includes total hostname/certificate counts, per-log tail positions,
    backfill completion percentages, and last tail sync times.
    """
    return await service.get_stats()
