"""Integration tests for ctpool.audit_queries — raw SQL gap detection queries.

All tests use the real ctpool_test database via the db_session fixture.
Every test rolls back automatically.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from ctpool.audit_queries import (
    query_failed_backfill_ranges,
    query_missing_entry_outcomes,
    query_missing_observations_without_outcome,
    query_stale_backfill_claims,
)
from ctpool.models.certificate import Certificate
from ctpool.models.entry_outcome import CtEntryOutcome
from ctpool.models.log_backfill_range import CtLogBackfillRange
from ctpool.models.log_source import CtLogSource
from ctpool.models.observation import CtLogObservation

pytestmark = pytest.mark.integration

_NOW = datetime.now(UTC)


def _make_source(url: str = "https://ct.example.com/log/") -> CtLogSource:
    return CtLogSource(
        id=uuid.uuid4(),
        log_id_b64="dGVzdA==",
        operator_name="Test Operator",
        description="Test CT Log",
        url=url,
        public_key_b64="a2V5==",
        log_state="usable",
        is_eligible_for_tail=True,
        is_eligible_for_backfill=True,
        source_list="chrome",
        first_seen_at=_NOW,
        last_synced_at=_NOW,
    )


def _make_range(
    source_id: uuid.UUID,
    *,
    start: int = 0,
    end: int = 99,
    status: str = "in_progress",
    claimed_by: str | None = "worker-1",
    claimed_at: datetime | None = None,
    heartbeat_at: datetime | None = None,
) -> CtLogBackfillRange:
    return CtLogBackfillRange(
        id=uuid.uuid4(),
        log_source_id=source_id,
        start_index=start,
        end_index=end,
        next_index=start,
        status=status,
        claimed_by=claimed_by,
        claimed_at=claimed_at or _NOW,
        heartbeat_at=heartbeat_at,
    )


# ---------------------------------------------------------------------------
# query_stale_backfill_claims
# ---------------------------------------------------------------------------


async def test_query_stale_backfill_claims_returns_stale_range(
    db_session: AsyncSession,
) -> None:
    """Returns in_progress ranges whose heartbeat is older than the timeout."""
    source = _make_source(url="https://stale1.example.com/")
    db_session.add(source)
    await db_session.flush()
    stale_range = _make_range(
        source.id,
        claimed_at=_NOW - timedelta(seconds=7200),
        heartbeat_at=_NOW - timedelta(seconds=7200),
    )
    db_session.add(stale_range)
    await db_session.flush()

    rows = await query_stale_backfill_claims(db_session, claim_timeout_seconds=3600)
    ids = [str(r["id"]) for r in rows]
    assert str(stale_range.id) in ids


async def test_query_stale_backfill_claims_ignores_fresh_range(
    db_session: AsyncSession,
) -> None:
    """Does not return ranges whose heartbeat is within the timeout window."""
    source = _make_source(url="https://fresh1.example.com/")
    db_session.add(source)
    await db_session.flush()
    fresh_range = _make_range(
        source.id,
        claimed_at=_NOW - timedelta(seconds=60),
        heartbeat_at=_NOW - timedelta(seconds=60),
    )
    db_session.add(fresh_range)
    await db_session.flush()

    rows = await query_stale_backfill_claims(db_session, claim_timeout_seconds=3600)
    ids = [str(r["id"]) for r in rows]
    assert str(fresh_range.id) not in ids


# ---------------------------------------------------------------------------
# query_failed_backfill_ranges
# ---------------------------------------------------------------------------


async def test_query_failed_backfill_ranges_returns_failed(
    db_session: AsyncSession,
) -> None:
    """Returns ranges with status=failed."""
    source = _make_source(url="https://failed1.example.com/")
    db_session.add(source)
    await db_session.flush()
    failed = _make_range(source.id, status="failed", claimed_by=None)
    db_session.add(failed)
    await db_session.flush()

    rows = await query_failed_backfill_ranges(db_session)
    ids = [str(r["id"]) for r in rows]
    assert str(failed.id) in ids


async def test_query_failed_backfill_ranges_ignores_complete(
    db_session: AsyncSession,
) -> None:
    """Does not return completed ranges."""
    source = _make_source(url="https://complete1.example.com/")
    db_session.add(source)
    await db_session.flush()
    complete = _make_range(source.id, status="complete", claimed_by=None)
    db_session.add(complete)
    await db_session.flush()

    rows = await query_failed_backfill_ranges(db_session)
    ids = [str(r["id"]) for r in rows]
    assert str(complete.id) not in ids


# ---------------------------------------------------------------------------
# query_missing_entry_outcomes
# ---------------------------------------------------------------------------


async def test_query_missing_entry_outcomes_returns_gap(
    db_session: AsyncSession,
) -> None:
    """Returns completed ranges with fewer outcome rows than expected."""
    source = _make_source(url="https://gap1.example.com/")
    db_session.add(source)
    await db_session.flush()
    rng = _make_range(source.id, start=0, end=4, status="complete", claimed_by=None)
    db_session.add(rng)
    await db_session.flush()
    # Add only 3 of the 5 expected outcomes
    for i in range(3):
        db_session.add(
            CtEntryOutcome(
                id=uuid.uuid4(),
                log_source_id=source.id,
                log_index=i,
                outcome="stored",
                first_seen_at=_NOW,
            )
        )
    await db_session.flush()

    rows = await query_missing_entry_outcomes(db_session)
    range_ids = [str(r["range_id"]) for r in rows]
    assert str(rng.id) in range_ids
    matching = next(r for r in rows if str(r["range_id"]) == str(rng.id))
    assert matching["missing_count"] == 2


async def test_query_missing_entry_outcomes_returns_empty_when_fully_covered(
    db_session: AsyncSession,
) -> None:
    """Returns empty list when all outcome rows are present."""
    source = _make_source(url="https://full1.example.com/")
    db_session.add(source)
    await db_session.flush()
    rng = _make_range(source.id, start=0, end=2, status="complete", claimed_by=None)
    db_session.add(rng)
    await db_session.flush()
    for i in range(3):
        db_session.add(
            CtEntryOutcome(
                id=uuid.uuid4(),
                log_source_id=source.id,
                log_index=i,
                outcome="stored",
                first_seen_at=_NOW,
            )
        )
    await db_session.flush()

    rows = await query_missing_entry_outcomes(db_session)
    range_ids = [str(r["range_id"]) for r in rows]
    assert str(rng.id) not in range_ids


# ---------------------------------------------------------------------------
# query_missing_observations_without_outcome
# ---------------------------------------------------------------------------


async def _make_certificate(session: AsyncSession) -> uuid.UUID:
    cert = Certificate(
        id=uuid.uuid4(),
        fingerprint_sha256="a" * 64,
        spki_sha256="b" * 64,
        serial_number="01",
        issuer_dn="CN=Test CA",
        subject_dn="CN=example.com",
        not_before=_NOW,
        not_after=_NOW,
        signature_algorithm_oid="1.2.840.113549.1.1.11",
        signature_algorithm_name="sha256WithRSAEncryption",
        public_key_algorithm_oid="1.2.840.113549.1.1.1",
        public_key_algorithm_name="rsaEncryption",
        is_precertificate=False,
        is_wildcard_present=False,
        san_count=1,
    )
    session.add(cert)
    await session.flush()
    return cert.id


async def test_query_missing_observations_without_outcome_returns_orphan(
    db_session: AsyncSession,
) -> None:
    """Returns observations that lack a matching outcome row."""
    source = _make_source(url="https://obs1.example.com/")
    db_session.add(source)
    await db_session.flush()
    cert_id = await _make_certificate(db_session)
    obs = CtLogObservation(
        id=uuid.uuid4(),
        log_source_id=source.id,
        certificate_id=cert_id,
        log_index=42,
        observed_at=_NOW,
    )
    db_session.add(obs)
    await db_session.flush()

    rows = await query_missing_observations_without_outcome(db_session)
    log_indices = [r["log_index"] for r in rows if r["log_source_id"] == source.id]
    assert 42 in log_indices


async def test_query_missing_observations_without_outcome_returns_empty_when_covered(
    db_session: AsyncSession,
) -> None:
    """Returns empty when every observation has a matching outcome row."""
    source = _make_source(url="https://obs2.example.com/")
    db_session.add(source)
    await db_session.flush()
    cert_id = await _make_certificate(db_session)
    obs = CtLogObservation(
        id=uuid.uuid4(),
        log_source_id=source.id,
        certificate_id=cert_id,
        log_index=99,
        observed_at=_NOW,
    )
    db_session.add(obs)
    db_session.add(
        CtEntryOutcome(
            id=uuid.uuid4(),
            log_source_id=source.id,
            log_index=99,
            outcome="stored",
            first_seen_at=_NOW,
        )
    )
    await db_session.flush()

    rows = await query_missing_observations_without_outcome(db_session)
    log_indices = [r["log_index"] for r in rows if r["log_source_id"] == source.id]
    assert 99 not in log_indices
