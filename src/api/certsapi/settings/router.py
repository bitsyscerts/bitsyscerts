"""Settings router: GET/PUT /v1/settings/storage and GET history."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from certsapi.database import get_db
from certsapi.settings.models import (
    StorageSettingsHistoryItem,
    StorageSettingsResponse,
    UpdateStorageSettingsRequest,
    UpdateStorageSettingsResult,
)
from certsapi.settings.repository import SettingsRepository
from certsapi.settings.service import SettingsService

settings_router = APIRouter(prefix="/v1/settings", tags=["settings"])


def _get_settings_repository(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> SettingsRepository:
    """Instantiate a SettingsRepository bound to the request-scoped session."""
    return SettingsRepository(session)


def _get_settings_service(
    repo: Annotated[SettingsRepository, Depends(_get_settings_repository)],
) -> SettingsService:
    """Instantiate a SettingsService with an injected repository."""
    return SettingsService(repo)


@settings_router.get(
    "/storage",
    response_model=StorageSettingsResponse,
    summary="Get active storage settings",
)
async def get_storage_settings(
    service: Annotated[SettingsService, Depends(_get_settings_service)],
) -> StorageSettingsResponse:
    """Return the active database-backed storage settings.

    Returns 404 if no settings row has been created yet
    (instance not yet bootstrapped).
    """
    result = await service.get_settings()
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No storage settings found. Run the worker to bootstrap.",
        )
    return result


@settings_router.put(
    "/storage",
    response_model=UpdateStorageSettingsResult,
    summary="Update active storage settings",
)
async def update_storage_settings(
    request: UpdateStorageSettingsRequest,
    service: Annotated[SettingsService, Depends(_get_settings_service)],
) -> UpdateStorageSettingsResult:
    """Replace the active storage settings with the provided configuration.

    Note: changing settings is prospective only.  Existing data is NOT
    automatically pruned or migrated when the profile changes.  Run the
    prune job manually if you wish to reclaim disk space.
    """
    try:
        return await service.update_settings(request)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc


@settings_router.get(
    "/storage/history",
    response_model=list[StorageSettingsHistoryItem],
    summary="Get storage settings change history",
)
async def get_storage_settings_history(
    service: Annotated[SettingsService, Depends(_get_settings_service)],
    limit: int = 50,
) -> list[StorageSettingsHistoryItem]:
    """Return the history of distinct storage settings configurations.

    Args:
        limit: Maximum number of history entries to return (default 50).
    """
    return await service.get_history(limit=limit)
