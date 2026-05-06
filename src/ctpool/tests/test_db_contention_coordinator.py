"""Tests for shared DB contention worker-facing coordination."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from sqlalchemy.exc import SQLAlchemyError

from ctpool.config import Settings
from ctpool.db_contention_coordinator import (
    get_db_contention_directive,
    submit_db_contention_observation,
)
from ctpool.db_contention_types import DbContentionObservation


def _settings(**overrides: object) -> Settings:
    base = {
        "database_url": "postgresql+psycopg://ctpool:ctpool@localhost:5432/ctpool_test",
        "ct_default_batch_size": 64,
        "ct_db_contention_enabled": True,
        "ct_db_contention_max_sleep_seconds": 5.0,
        "ct_db_contention_min_batch_size": 16,
    }
    base.update(overrides)
    return Settings.model_validate(base)


def _session_factory() -> MagicMock:
    session = AsyncMock()
    session.begin = MagicMock()
    session.begin.return_value.__aenter__ = AsyncMock(return_value=None)
    session.begin.return_value.__aexit__ = AsyncMock(return_value=False)
    factory = MagicMock()
    factory.return_value.__aenter__ = AsyncMock(return_value=session)
    factory.return_value.__aexit__ = AsyncMock(return_value=False)
    return factory


async def test_get_db_contention_directive_degrades_on_sqlalchemy_error() -> None:
    settings = _settings()
    with patch(
        "ctpool.db_contention_coordinator.load_db_contention_directive",
        AsyncMock(side_effect=SQLAlchemyError("boom")),
    ):
        directive = await get_db_contention_directive(
            _session_factory(),
            settings,
            requested_batch_size=64,
        )

    assert directive.base_sleep_seconds == 5.0
    assert directive.batch_size_cap == 16


async def test_submit_db_contention_observation_degrades_on_sqlalchemy_error() -> None:
    settings = _settings()
    observation = DbContentionObservation(entries_attempted=3, retryable_errors=1)
    with patch(
        "ctpool.db_contention_coordinator.merge_db_contention_observation",
        AsyncMock(side_effect=SQLAlchemyError("boom")),
    ):
        directive = await submit_db_contention_observation(
            _session_factory(),
            settings,
            observation,
            requested_batch_size=64,
        )

    assert directive.base_sleep_seconds == 5.0
    assert directive.batch_size_cap == 16
