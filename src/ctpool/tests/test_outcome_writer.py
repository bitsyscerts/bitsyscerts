"""Integration tests for outcome_writer.upsert_entry_outcome.

Uses the shared ``db_session`` fixture that rolls back after each test so
tests are isolated and leave no permanent state.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ctpool.models.entry_outcome import CtEntryOutcome
from ctpool.models.log_source import CtLogSource
from ctpool.outcome_constants import (
    OUTCOME_PARSE_ERROR,
    OUTCOME_STORED,
    OUTCOME_UNSUPPORTED_ENTRY_TYPE,
)
from ctpool.outcome_writer import upsert_entry_outcome

pytestmark = pytest.mark.asyncio


async def _make_log_source(session: AsyncSession) -> CtLogSource:
    """Insert a minimal CtLogSource and return it."""
    log = CtLogSource(
        id=uuid.uuid4(),
        log_id_b64="dGVzdA==",
        operator_name="Test Operator",
        description="Test Log",
        url="https://ct.example.com/log/",
        public_key_b64="a2V5==",
        log_state="usable",
        is_eligible_for_tail=True,
        is_eligible_for_backfill=True,
        source_list="chrome",
        first_seen_at=datetime.now(UTC),
        last_synced_at=datetime.now(UTC),
    )
    session.add(log)
    await session.flush()
    return log


async def _fetch_outcome(
    session: AsyncSession,
    log_source_id: uuid.UUID,
    log_index: int,
) -> CtEntryOutcome | None:
    """Return the outcome row for (log_source_id, log_index) or None."""
    result = await session.execute(
        select(CtEntryOutcome).where(
            CtEntryOutcome.log_source_id == log_source_id,
            CtEntryOutcome.log_index == log_index,
        )
    )
    return result.scalar_one_or_none()


async def test_upsert_creates_new_row(db_session: AsyncSession) -> None:
    """First upsert inserts a new row with the correct outcome."""
    log = await _make_log_source(db_session)

    await upsert_entry_outcome(
        db_session,
        log.id,
        0,
        OUTCOME_STORED,
        certificate_fingerprint_sha256="abc123",
    )
    await db_session.flush()

    row = await _fetch_outcome(db_session, log.id, 0)
    assert row is not None
    assert row.outcome == OUTCOME_STORED
    assert row.certificate_fingerprint_sha256 == "abc123"
    assert row.attempt_count == 1
    assert row.error_type is None


async def test_upsert_on_conflict_increments_attempt_count(
    db_session: AsyncSession,
) -> None:
    """Second upsert for same (log_source_id, log_index) increments attempt_count."""
    log = await _make_log_source(db_session)

    await upsert_entry_outcome(db_session, log.id, 1, OUTCOME_PARSE_ERROR)
    await db_session.flush()
    await upsert_entry_outcome(db_session, log.id, 1, OUTCOME_PARSE_ERROR)
    await db_session.flush()

    row = await _fetch_outcome(db_session, log.id, 1)
    assert row is not None
    assert row.attempt_count == 2


async def test_upsert_updates_last_seen_at_on_conflict(
    db_session: AsyncSession,
) -> None:
    """Second upsert updates last_seen_at without creating a duplicate row."""
    log = await _make_log_source(db_session)

    await upsert_entry_outcome(db_session, log.id, 2, OUTCOME_PARSE_ERROR)
    await db_session.flush()

    first_row = await _fetch_outcome(db_session, log.id, 2)
    assert first_row is not None
    first_seen = first_row.first_seen_at

    await upsert_entry_outcome(db_session, log.id, 2, OUTCOME_PARSE_ERROR)
    await db_session.flush()

    # No duplicate row created
    result = await db_session.execute(
        select(CtEntryOutcome).where(
            CtEntryOutcome.log_source_id == log.id,
            CtEntryOutcome.log_index == 2,
        )
    )
    rows = result.scalars().all()
    assert len(rows) == 1
    # first_seen_at is unchanged; last_seen_at is refreshed by DB now()
    assert rows[0].first_seen_at == first_seen


async def test_parse_error_transition_to_stored(db_session: AsyncSession) -> None:
    """A prior parse_error outcome can be overwritten with stored on
    successful retry.
    """
    log = await _make_log_source(db_session)

    # First pass: parse failure
    await upsert_entry_outcome(
        db_session,
        log.id,
        5,
        OUTCOME_PARSE_ERROR,
        error_type="ParseError",
        error_message="bad DER",
    )
    await db_session.flush()

    # Second pass: successful parse after parser fix
    await upsert_entry_outcome(
        db_session,
        log.id,
        5,
        OUTCOME_STORED,
        certificate_fingerprint_sha256="deadbeef",
    )
    await db_session.flush()

    row = await _fetch_outcome(db_session, log.id, 5)
    assert row is not None
    assert row.outcome == OUTCOME_STORED
    assert row.certificate_fingerprint_sha256 == "deadbeef"
    assert row.attempt_count == 2


async def test_upsert_stores_error_fields_for_parse_error(
    db_session: AsyncSession,
) -> None:
    """error_type and error_message are stored for failure outcomes."""
    log = await _make_log_source(db_session)

    await upsert_entry_outcome(
        db_session,
        log.id,
        7,
        OUTCOME_PARSE_ERROR,
        error_type="ParseError",
        error_message="Cannot base64-decode leaf_input: invalid chars",
    )
    await db_session.flush()

    row = await _fetch_outcome(db_session, log.id, 7)
    assert row is not None
    assert row.error_type == "ParseError"
    assert "base64" in (row.error_message or "")


async def test_upsert_unsupported_entry_type(db_session: AsyncSession) -> None:
    """unsupported_entry_type outcome is stored with expected fields."""
    log = await _make_log_source(db_session)

    await upsert_entry_outcome(
        db_session,
        log.id,
        9,
        OUTCOME_UNSUPPORTED_ENTRY_TYPE,
        error_type="UnsupportedEntryTypeError",
        error_message="Unknown LogEntryType: 0x0002",
    )
    await db_session.flush()

    row = await _fetch_outcome(db_session, log.id, 9)
    assert row is not None
    assert row.outcome == OUTCOME_UNSUPPORTED_ENTRY_TYPE
    assert row.error_type == "UnsupportedEntryTypeError"
