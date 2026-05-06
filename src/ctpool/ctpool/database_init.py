"""Orchestrate create, migrate, and force-reset flows for the target database."""

from __future__ import annotations

import asyncio
from typing import Literal

from sqlalchemy.exc import SQLAlchemyError

from ctpool.config import Settings
from ctpool.database_admin import (
    create_database_if_missing_sync,
    database_exists_sync,
    recreate_database_sync,
)
from ctpool.exceptions import DatabaseInitError
from ctpool.migration_runner import (
    get_current_revision,
    get_missing_core_tables,
    run_upgrade_head,
)

DatabaseInitState = Literal["missing", "ready", "inconsistent"]
DatabaseInitAction = Literal["created", "migrated", "recreated"]


async def classify_target_database_state(settings: Settings) -> DatabaseInitState:
    """Classify the target database for init-db orchestration."""
    try:
        revision = await get_current_revision(settings)
    except SQLAlchemyError as exc:
        loop = asyncio.get_running_loop()
        exists = await loop.run_in_executor(None, database_exists_sync, settings)
        if exists:
            raise DatabaseInitError(
                "Unable to connect to the target database with DATABASE_URL. "
                "Check the application connection settings before running init-db."
            ) from exc
        return "missing"

    if revision is None:
        return "ready"
    missing_tables = await get_missing_core_tables(settings)
    if missing_tables:
        return "inconsistent"
    return "ready"


async def run_init_db(
    settings: Settings,
    *,
    force: bool = False,
) -> DatabaseInitAction:
    """Ensure or forcibly recreate the target database, then apply migrations."""
    loop = asyncio.get_running_loop()
    if force:
        existed = await loop.run_in_executor(None, recreate_database_sync, settings)
        await run_upgrade_head(settings)
        return "recreated" if existed else "created"

    state = await classify_target_database_state(settings)
    if state == "inconsistent":
        raise DatabaseInitError(
            "Database exists but schema state is inconsistent. Run "
            "`ctpool init-db --force` to drop and recreate it."
        )
    if state == "missing":
        await loop.run_in_executor(None, create_database_if_missing_sync, settings)
        await run_upgrade_head(settings)
        return "created"

    await run_upgrade_head(settings)
    return "migrated"
