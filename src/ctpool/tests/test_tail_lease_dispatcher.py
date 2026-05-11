"""Integration tests for the persistent tail-lease dispatcher functions.

Tests cover claim_tail_log, release_tail_log, heartbeat_tail_lease,
and reap_stale_tail_leases against a real test database.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from ctpool.dispatcher_tail import (
    claim_tail_log,
    heartbeat_tail_lease,
    reap_stale_tail_leases,
    release_tail_log,
)
from ctpool.models import CtLogSource
from ctpool.models.log_tail_lease import CtLogTailLease

_STALE_SECS = 60
_WORKER_A = "host-a:1001"
_WORKER_B = "host-b:1002"


@pytest_asyncio.fixture()
async def log_source(
    db_session: AsyncSession, ct_log_source_factory: object
) -> CtLogSource:
    """Persist a single CtLogSource row and return it."""
    row: CtLogSource = ct_log_source_factory()  # type: ignore[operator]
    db_session.add(row)
    await db_session.flush()
    return row


async def _get_lease(session: AsyncSession, log_id: object) -> CtLogTailLease | None:
    from sqlalchemy import select

    result = await session.execute(
        select(CtLogTailLease).where(CtLogTailLease.log_source_id == log_id)
    )
    return result.scalars().first()


# ---------------------------------------------------------------------------
# claim_tail_log
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_claim_returns_true_for_first_worker(
    db_session: AsyncSession, log_source: CtLogSource
) -> None:
    """First claim on an unclaimed log returns True and persists the lease."""
    result = await claim_tail_log(db_session, log_source.id, _WORKER_A, _STALE_SECS)

    assert result is True
    lease = await _get_lease(db_session, log_source.id)
    assert lease is not None
    assert lease.claimed_by == _WORKER_A


@pytest.mark.asyncio
async def test_second_worker_cannot_claim_same_log(
    db_session: AsyncSession, log_source: CtLogSource
) -> None:
    """A fresh lease held by worker A blocks worker B."""
    await claim_tail_log(db_session, log_source.id, _WORKER_A, _STALE_SECS)

    result = await claim_tail_log(db_session, log_source.id, _WORKER_B, _STALE_SECS)

    assert result is False
    lease = await _get_lease(db_session, log_source.id)
    assert lease is not None
    assert lease.claimed_by == _WORKER_A


@pytest.mark.asyncio
async def test_stale_lease_can_be_stolen(
    db_session: AsyncSession, log_source: CtLogSource
) -> None:
    """A lease whose heartbeat is older than stale_seconds can be stolen."""
    stale_time = datetime.now(UTC) - timedelta(seconds=_STALE_SECS + 10)
    lease = CtLogTailLease(
        log_source_id=log_source.id,
        claimed_by=_WORKER_A,
        claimed_at=stale_time,
        heartbeat_at=stale_time,
    )
    db_session.add(lease)
    await db_session.flush()

    result = await claim_tail_log(db_session, log_source.id, _WORKER_B, _STALE_SECS)

    assert result is True
    await db_session.refresh(lease)
    assert lease.claimed_by == _WORKER_B


@pytest.mark.asyncio
async def test_claim_is_idempotent_same_worker(
    db_session: AsyncSession, log_source: CtLogSource
) -> None:
    """Same worker claiming twice returns True without corrupting the lease."""
    await claim_tail_log(db_session, log_source.id, _WORKER_A, _STALE_SECS)
    result = await claim_tail_log(db_session, log_source.id, _WORKER_A, _STALE_SECS)

    assert result is True
    lease = await _get_lease(db_session, log_source.id)
    assert lease is not None
    assert lease.claimed_by == _WORKER_A


# ---------------------------------------------------------------------------
# release_tail_log
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_release_clears_lease(
    db_session: AsyncSession, log_source: CtLogSource
) -> None:
    """After release by the owning worker, claimed_by becomes NULL."""
    await claim_tail_log(db_session, log_source.id, _WORKER_A, _STALE_SECS)
    await release_tail_log(db_session, log_source.id, _WORKER_A)

    lease = await _get_lease(db_session, log_source.id)
    assert lease is not None
    assert lease.claimed_by is None


@pytest.mark.asyncio
async def test_release_ignores_other_workers_lease(
    db_session: AsyncSession, log_source: CtLogSource
) -> None:
    """Worker B cannot release a lease held by worker A."""
    await claim_tail_log(db_session, log_source.id, _WORKER_A, _STALE_SECS)
    await release_tail_log(db_session, log_source.id, _WORKER_B)

    lease = await _get_lease(db_session, log_source.id)
    assert lease is not None
    assert lease.claimed_by == _WORKER_A


# ---------------------------------------------------------------------------
# heartbeat_tail_lease
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_heartbeat_updates_heartbeat_at(
    db_session: AsyncSession, log_source: CtLogSource
) -> None:
    """heartbeat_tail_lease advances heartbeat_at for the owning worker."""
    old_time = datetime.now(UTC) - timedelta(seconds=30)
    lease = CtLogTailLease(
        log_source_id=log_source.id,
        claimed_by=_WORKER_A,
        claimed_at=old_time,
        heartbeat_at=old_time,
    )
    db_session.add(lease)
    await db_session.flush()

    await heartbeat_tail_lease(db_session, log_source.id, _WORKER_A)
    await db_session.refresh(lease)

    assert lease.heartbeat_at is not None
    assert lease.heartbeat_at.replace(tzinfo=UTC) > old_time


@pytest.mark.asyncio
async def test_heartbeat_no_op_for_non_owner(
    db_session: AsyncSession, log_source: CtLogSource
) -> None:
    """heartbeat_tail_lease does nothing when the caller is not the owner."""
    old_time = datetime.now(UTC) - timedelta(seconds=30)
    lease = CtLogTailLease(
        log_source_id=log_source.id,
        claimed_by=_WORKER_A,
        claimed_at=old_time,
        heartbeat_at=old_time,
    )
    db_session.add(lease)
    await db_session.flush()

    await heartbeat_tail_lease(db_session, log_source.id, _WORKER_B)
    await db_session.refresh(lease)

    refreshed = lease.heartbeat_at
    assert refreshed is not None
    assert refreshed.replace(tzinfo=UTC) <= old_time + timedelta(seconds=1)


# ---------------------------------------------------------------------------
# reap_stale_tail_leases
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reap_releases_expired_lease(
    db_session: AsyncSession, log_source: CtLogSource
) -> None:
    """Reap clears leases whose heartbeat is older than stale_seconds."""
    stale_time = datetime.now(UTC) - timedelta(seconds=_STALE_SECS + 10)
    lease = CtLogTailLease(
        log_source_id=log_source.id,
        claimed_by=_WORKER_A,
        claimed_at=stale_time,
        heartbeat_at=stale_time,
    )
    db_session.add(lease)
    await db_session.flush()

    count = await reap_stale_tail_leases(db_session, _STALE_SECS)

    assert count == 1
    await db_session.refresh(lease)
    assert lease.claimed_by is None


@pytest.mark.asyncio
async def test_reap_does_not_release_fresh_lease(
    db_session: AsyncSession, log_source: CtLogSource
) -> None:
    """Reap leaves a recently-heartbeated lease untouched."""
    await claim_tail_log(db_session, log_source.id, _WORKER_A, _STALE_SECS)

    count = await reap_stale_tail_leases(db_session, _STALE_SECS)

    assert count == 0
    lease = await _get_lease(db_session, log_source.id)
    assert lease is not None
    assert lease.claimed_by == _WORKER_A


@pytest.mark.asyncio
async def test_reap_returns_correct_count_multiple(
    db_session: AsyncSession, ct_log_source_factory: object
) -> None:
    """Reap returns the count of all rows reset when multiple are stale."""
    stale_time = datetime.now(UTC) - timedelta(seconds=_STALE_SECS + 10)

    for i in range(3):
        log: CtLogSource = ct_log_source_factory(  # type: ignore[operator]
            url=f"https://ct.example.com/log-multi-{i}/",
            log_id_b64=f"bXVsdGktbG9nLXt7aX19=={i}",
        )
        db_session.add(log)
        await db_session.flush()
        lease = CtLogTailLease(
            log_source_id=log.id,
            claimed_by=_WORKER_A,
            claimed_at=stale_time,
            heartbeat_at=stale_time,
        )
        db_session.add(lease)
        await db_session.flush()

    count = await reap_stale_tail_leases(db_session, _STALE_SECS)

    assert count == 3
