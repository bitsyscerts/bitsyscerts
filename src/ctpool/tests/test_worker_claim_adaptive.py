"""Tests for the adaptive window additions to ctpool.worker_claim.

Covers:
    extend_window_backward  — moves start, increments counter, updates oldest
    update_observed_oldest  — persists only when strictly older
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from ctpool.models.log_backfill_state import CtLogBackfillState
from ctpool.worker_claim import (
    ensure_log_backfill_state,
    extend_window_backward,
    initialize_log_window,
    update_observed_oldest,
)

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _insert_log_source(session: AsyncSession) -> uuid.UUID:
    log_id = uuid.uuid4()
    await session.execute(
        text(
            """
            INSERT INTO ct_log_sources
                (id, log_id_b64, operator_name, description, url,
                 public_key_b64, log_state, is_eligible_for_tail,
                 is_eligible_for_backfill, source_list)
            VALUES
                (:id, :log_id_b64, 'Op', 'Test Log', 'https://ct.example.com/',
                 'a2V5', 'usable', true, true, 'chrome')
            """
        ).bindparams(id=log_id, log_id_b64=f"log-{log_id}")
    )
    return log_id


async def _setup_row(session: AsyncSession) -> uuid.UUID:
    """Insert a log source and ensure a backfill state row exists."""
    log_id = await _insert_log_source(session)
    async with session.begin_nested():
        await ensure_log_backfill_state(session, log_source_id=log_id)
        await initialize_log_window(
            session,
            log_source_id=log_id,
            backfill_start_index=10_000,
            backfill_end_index=100_000,
        )
        await session.flush()
    return log_id


async def _fetch(session: AsyncSession, log_id: uuid.UUID) -> CtLogBackfillState:
    result = await session.execute(
        select(CtLogBackfillState).where(CtLogBackfillState.log_source_id == log_id)
    )
    row = result.scalar_one()
    await session.refresh(row)
    return row


_UTC = UTC
_OLD = datetime(2020, 1, 1, tzinfo=_UTC)
_OLDER = datetime(2019, 1, 1, tzinfo=_UTC)
_NEWER = datetime(2021, 1, 1, tzinfo=_UTC)


# ---------------------------------------------------------------------------
# extend_window_backward
# ---------------------------------------------------------------------------


async def test_extend_sets_new_start_index(db_session: AsyncSession) -> None:
    """extend_window_backward updates backfill_start_index to new_start."""
    log_id = await _setup_row(db_session)

    async with db_session.begin_nested():
        await extend_window_backward(
            db_session, log_source_id=log_id, new_start=5_000, observed_oldest=None
        )
        await db_session.flush()

    row = await _fetch(db_session, log_id)
    assert row.backfill_start_index == 5_000


async def test_extend_sets_last_checkpoint_index(db_session: AsyncSession) -> None:
    """extend_window_backward also resets last_checkpoint_index to new_start."""
    log_id = await _setup_row(db_session)

    async with db_session.begin_nested():
        await extend_window_backward(
            db_session, log_source_id=log_id, new_start=3_000, observed_oldest=None
        )
        await db_session.flush()

    row = await _fetch(db_session, log_id)
    assert row.last_checkpoint_index == 3_000


async def test_extend_increments_window_extended_count(
    db_session: AsyncSession,
) -> None:
    """extend_window_backward increments window_extended_count on each call."""
    log_id = await _setup_row(db_session)

    async with db_session.begin_nested():
        await extend_window_backward(
            db_session, log_source_id=log_id, new_start=8_000, observed_oldest=None
        )
        await db_session.flush()

    row = await _fetch(db_session, log_id)
    assert row.window_extended_count == 1

    async with db_session.begin_nested():
        await extend_window_backward(
            db_session, log_source_id=log_id, new_start=4_000, observed_oldest=None
        )
        await db_session.flush()

    row = await _fetch(db_session, log_id)
    assert row.window_extended_count == 2


async def test_extend_sets_observed_oldest_when_none_stored(
    db_session: AsyncSession,
) -> None:
    """extend_window_backward sets observed_oldest_not_before when column is NULL."""
    log_id = await _setup_row(db_session)

    async with db_session.begin_nested():
        await extend_window_backward(
            db_session, log_source_id=log_id, new_start=5_000, observed_oldest=_OLD
        )
        await db_session.flush()

    row = await _fetch(db_session, log_id)
    assert row.observed_oldest_not_before is not None
    assert row.observed_oldest_not_before.replace(tzinfo=_UTC) == _OLD


async def test_extend_does_not_overwrite_with_none(db_session: AsyncSession) -> None:
    """extend_window_backward with observed_oldest=None preserves existing value."""
    log_id = await _setup_row(db_session)

    async with db_session.begin_nested():
        await update_observed_oldest(
            db_session, log_source_id=log_id, oldest_not_before=_OLD
        )
        await db_session.flush()

    async with db_session.begin_nested():
        await extend_window_backward(
            db_session, log_source_id=log_id, new_start=5_000, observed_oldest=None
        )
        await db_session.flush()

    row = await _fetch(db_session, log_id)
    assert row.observed_oldest_not_before is not None


# ---------------------------------------------------------------------------
# update_observed_oldest
# ---------------------------------------------------------------------------


async def test_update_sets_oldest_when_column_is_null(db_session: AsyncSession) -> None:
    """update_observed_oldest writes the date when nothing is stored yet."""
    log_id = await _setup_row(db_session)

    async with db_session.begin_nested():
        await update_observed_oldest(
            db_session, log_source_id=log_id, oldest_not_before=_OLD
        )
        await db_session.flush()

    row = await _fetch(db_session, log_id)
    assert row.observed_oldest_not_before is not None


async def test_update_replaces_with_strictly_older_date(
    db_session: AsyncSession,
) -> None:
    """update_observed_oldest updates the stored value when new date is older."""
    log_id = await _setup_row(db_session)

    async with db_session.begin_nested():
        await update_observed_oldest(
            db_session, log_source_id=log_id, oldest_not_before=_OLD
        )
        await db_session.flush()

    async with db_session.begin_nested():
        await update_observed_oldest(
            db_session, log_source_id=log_id, oldest_not_before=_OLDER
        )
        await db_session.flush()

    row = await _fetch(db_session, log_id)
    stored = row.observed_oldest_not_before
    assert stored is not None
    stored_aware = stored.replace(tzinfo=_UTC) if stored.tzinfo is None else stored
    assert stored_aware == _OLDER


async def test_update_ignores_newer_date(db_session: AsyncSession) -> None:
    """update_observed_oldest does not replace the stored value with a newer date."""
    log_id = await _setup_row(db_session)

    async with db_session.begin_nested():
        await update_observed_oldest(
            db_session, log_source_id=log_id, oldest_not_before=_OLD
        )
        await db_session.flush()

    async with db_session.begin_nested():
        await update_observed_oldest(
            db_session, log_source_id=log_id, oldest_not_before=_NEWER
        )
        await db_session.flush()

    row = await _fetch(db_session, log_id)
    stored = row.observed_oldest_not_before
    assert stored is not None
    stored_aware = stored.replace(tzinfo=_UTC) if stored.tzinfo is None else stored
    assert stored_aware == _OLD
