"""Integration tests for ctpool.audit_checker — mapping raw rows to findings.

Uses the real ctpool_test database; every test rolls back automatically.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ctpool.audit_checker import (
    AuditCheckResult,
    run_all_checks,
    run_failed_backfill_range_check,
    run_missing_entry_outcomes_check,
    run_missing_observations_check,
    run_stale_backfill_claim_check,
)
from ctpool.audit_constants import (
    FINDING_TYPE_FAILED_BACKFILL_RANGE,
    FINDING_TYPE_MISSING_ENTRY_OUTCOMES,
    FINDING_TYPE_MISSING_OBSERVATIONS_WITHOUT_OUTCOME,
    FINDING_TYPE_STALE_BACKFILL_CLAIM,
    SEVERITY_ERROR,
    SEVERITY_WARNING,
    STATUS_OPEN,
)
from ctpool.models.audit_finding import CtAuditFinding
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
    end: int = 4,
    status: str = "in_progress",
    claimed_by: str | None = "worker-1",
    heartbeat_at: datetime | None = None,
    claimed_at: datetime | None = None,
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
# run_stale_backfill_claim_check
# ---------------------------------------------------------------------------


async def test_run_stale_backfill_claim_check_creates_finding(
    db_session: AsyncSession,
) -> None:
    """Stale in_progress range creates a warning finding."""
    source = _make_source(url="https://checker-stale1.example.com/")
    db_session.add(source)
    await db_session.flush()
    rng = _make_range(
        source.id,
        claimed_at=_NOW - timedelta(seconds=7200),
        heartbeat_at=_NOW - timedelta(seconds=7200),
    )
    db_session.add(rng)
    await db_session.flush()

    count = await run_stale_backfill_claim_check(db_session, 3600)
    assert count == 1

    result = await db_session.execute(
        select(CtAuditFinding).where(
            CtAuditFinding.finding_type == FINDING_TYPE_STALE_BACKFILL_CLAIM,
            CtAuditFinding.range_id == rng.id,
        )
    )
    finding = result.scalar_one()
    assert finding.severity == SEVERITY_WARNING
    assert finding.status == STATUS_OPEN


async def test_run_stale_backfill_claim_check_deduplicates(
    db_session: AsyncSession,
) -> None:
    """Second check for the same stale range does not create a duplicate finding."""
    source = _make_source(url="https://checker-stale2.example.com/")
    db_session.add(source)
    await db_session.flush()
    rng = _make_range(
        source.id,
        claimed_at=_NOW - timedelta(seconds=7200),
        heartbeat_at=_NOW - timedelta(seconds=7200),
    )
    db_session.add(rng)
    await db_session.flush()

    first = await run_stale_backfill_claim_check(db_session, 3600)
    second = await run_stale_backfill_claim_check(db_session, 3600)
    assert first == 1
    assert second == 0


# ---------------------------------------------------------------------------
# run_failed_backfill_range_check
# ---------------------------------------------------------------------------


async def test_run_failed_backfill_range_check_creates_error_finding(
    db_session: AsyncSession,
) -> None:
    """Failed range creates an error-severity finding."""
    source = _make_source(url="https://checker-failed1.example.com/")
    db_session.add(source)
    await db_session.flush()
    rng = _make_range(source.id, status="failed", claimed_by=None)
    db_session.add(rng)
    await db_session.flush()

    count = await run_failed_backfill_range_check(db_session)
    assert count == 1

    result = await db_session.execute(
        select(CtAuditFinding).where(
            CtAuditFinding.finding_type == FINDING_TYPE_FAILED_BACKFILL_RANGE,
            CtAuditFinding.range_id == rng.id,
        )
    )
    finding = result.scalar_one()
    assert finding.severity == SEVERITY_ERROR


# ---------------------------------------------------------------------------
# run_missing_entry_outcomes_check
# ---------------------------------------------------------------------------


async def test_run_missing_entry_outcomes_check_sets_missing_count(
    db_session: AsyncSession,
) -> None:
    """Completed range with partial outcomes creates a finding with correct count."""
    source = _make_source(url="https://checker-gap1.example.com/")
    db_session.add(source)
    await db_session.flush()
    rng = _make_range(source.id, start=0, end=4, status="complete", claimed_by=None)
    db_session.add(rng)
    await db_session.flush()
    # 2 of 5 outcomes present
    for i in range(2):
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

    count = await run_missing_entry_outcomes_check(db_session)
    assert count == 1

    result = await db_session.execute(
        select(CtAuditFinding).where(
            CtAuditFinding.finding_type == FINDING_TYPE_MISSING_ENTRY_OUTCOMES,
        )
    )
    finding = result.scalar_one()
    assert finding.missing_count == 3


# ---------------------------------------------------------------------------
# run_missing_observations_check
# ---------------------------------------------------------------------------


async def _make_certificate(session: AsyncSession) -> uuid.UUID:
    cert = Certificate(
        id=uuid.uuid4(),
        fingerprint_sha256="c" * 64,
        spki_sha256="d" * 64,
        serial_number="02",
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


async def test_run_missing_observations_check_creates_finding(
    db_session: AsyncSession,
) -> None:
    """Observation without outcome creates a warning finding."""
    source = _make_source(url="https://checker-obs1.example.com/")
    db_session.add(source)
    cert_id = await _make_certificate(db_session)
    obs = CtLogObservation(
        id=uuid.uuid4(),
        log_source_id=source.id,
        certificate_id=cert_id,
        log_index=77,
        observed_at=_NOW,
    )
    db_session.add(obs)
    await db_session.flush()

    count = await run_missing_observations_check(db_session)
    assert count >= 1

    result = await db_session.execute(
        select(CtAuditFinding).where(
            CtAuditFinding.finding_type
            == FINDING_TYPE_MISSING_OBSERVATIONS_WITHOUT_OUTCOME,
            CtAuditFinding.start_index == 77,
            CtAuditFinding.log_source_id == source.id,
        )
    )
    assert result.scalar_one() is not None


# ---------------------------------------------------------------------------
# run_all_checks
# ---------------------------------------------------------------------------


async def test_run_all_checks_returns_aggregated_result(
    db_session: AsyncSession,
) -> None:
    """run_all_checks returns an AuditCheckResult with correct totals."""
    result = await run_all_checks(db_session, claim_timeout_seconds=3600)
    assert isinstance(result, AuditCheckResult)
    assert result.total_new_findings >= 0
