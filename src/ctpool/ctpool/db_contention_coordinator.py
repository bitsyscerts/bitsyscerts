"""Worker-facing helpers for shared DB contention pacing."""

from __future__ import annotations

import asyncio
import logging
import random
from collections.abc import Callable

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ctpool.config import Settings
from ctpool.db_contention_accumulator import DbRetryPressureAccumulator
from ctpool.db_contention_store import (
    baseline_db_contention_directive,
    degraded_db_contention_directive,
    load_db_contention_directive,
    merge_db_contention_observation,
)
from ctpool.db_contention_types import DbContentionDirective, DbContentionObservation

_logger = logging.getLogger(__name__)


async def get_db_contention_directive(
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
    requested_batch_size: int,
) -> DbContentionDirective:
    """Load the current shared pacing hint, degrading safely on failures."""
    if not settings.ct_db_contention_enabled:
        return baseline_db_contention_directive()
    try:
        async with session_factory() as session:
            return await load_db_contention_directive(
                session,
                settings,
                requested_batch_size,
            )
    except SQLAlchemyError as exc:  # pragma: no cover
        _logger.warning(
            "db contention read unavailable exception_type=%s",
            exc.__class__.__name__,
        )
        return degraded_db_contention_directive(settings, requested_batch_size)


async def submit_db_contention_observation(
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
    observation: DbContentionObservation,
    requested_batch_size: int,
) -> DbContentionDirective:
    """Publish one boundary observation, degrading safely on failures."""
    if not settings.ct_db_contention_enabled or not observation.has_activity:
        return baseline_db_contention_directive()
    try:
        async with session_factory() as session:
            async with session.begin():
                return await merge_db_contention_observation(
                    session,
                    settings,
                    observation,
                    requested_batch_size,
                )
    except SQLAlchemyError as exc:  # pragma: no cover
        _logger.warning(
            "db contention write unavailable exception_type=%s",
            exc.__class__.__name__,
        )
        return degraded_db_contention_directive(settings, requested_batch_size)


def build_db_retry_callback(
    accumulator: DbRetryPressureAccumulator,
    callback: Callable[[int, BaseException, float], None] | None,
) -> Callable[[int, BaseException, float], None]:
    """Return a retry callback that records pressure before delegating."""
    return accumulator.wrap_retry_callback(callback)


def resolve_effective_batch_size(
    requested_batch_size: int,
    directive: DbContentionDirective,
) -> int:
    """Clamp the requested batch size against the shared DB-pressure cap."""
    if directive.batch_size_cap is None:
        return requested_batch_size
    return max(1, min(requested_batch_size, directive.batch_size_cap))


async def sleep_for_db_contention(
    directive: DbContentionDirective,
    settings: Settings,
) -> float:
    """Sleep for the current shared pacing delay plus worker-local jitter."""
    if directive.base_sleep_seconds <= 0.0:
        return 0.0
    jitter = directive.base_sleep_seconds * settings.ct_db_contention_jitter_fraction
    delay = directive.base_sleep_seconds + random.uniform(0.0, jitter)  # noqa: S311
    await asyncio.sleep(delay)
    return delay
