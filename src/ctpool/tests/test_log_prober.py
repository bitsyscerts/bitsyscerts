"""Tests for ctpool.log_prober — probe_log.

Uses pytest-httpx to mock HTTP calls and the real ``ctpool_test`` DB via
``db_session`` to verify runtime state persistence.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import httpx
import pytest
from pytest_httpx import HTTPXMock
from sqlalchemy.ext.asyncio import AsyncSession

from ctpool.log_prober import probe_log
from ctpool.models.log_source import CtLogSource

pytestmark = pytest.mark.integration

_STH_URL_SUFFIX = "/ct/v1/get-sth"

_SAMPLE_STH = {
    "tree_size": 12345,
    "timestamp": 1704067200000,
    "sha256_root_hash": "abc123==",
    "tree_head_signature": "sig==",
}


def _make_log_source(
    *,
    url: str = "https://ct.example.com/log/",
    log_id: str = "dGVzdA==",
) -> CtLogSource:
    return CtLogSource(
        id=uuid.uuid4(),
        log_id_b64=log_id,
        operator_name="Test Operator",
        description="Test CT Log",
        url=url,
        public_key_b64="a2V5==",
        log_state="usable",
        is_eligible_for_tail=True,
        is_eligible_for_backfill=True,
        source_list="chrome",
        first_seen_at=datetime.now(UTC),
        last_synced_at=datetime.now(UTC),
    )


# ---------------------------------------------------------------------------
# Successful probe
# ---------------------------------------------------------------------------


async def test_probe_log_success_sets_health_ok(
    db_session: AsyncSession,
    httpx_mock: HTTPXMock,
) -> None:
    """On 200, health_status is set to 'ok' and tree_size is stored."""
    source = _make_log_source()
    db_session.add(source)
    await db_session.flush()

    httpx_mock.add_response(
        url=f"{source.url.rstrip('/')}{_STH_URL_SUFFIX}",
        json=_SAMPLE_STH,
        status_code=200,
    )
    async with httpx.AsyncClient() as client:
        state = await probe_log(source, client, db_session)

    assert state.health_status == "ok"
    assert state.tree_size == 12345
    assert state.last_success_at is not None
    assert state.last_probe_at is not None
    assert state.consecutive_failures == 0


async def test_probe_log_success_resets_consecutive_failures(
    db_session: AsyncSession,
    httpx_mock: HTTPXMock,
) -> None:
    """After a success, consecutive_failures is reset to 0."""
    source = _make_log_source(url="https://ct2.example.com/log/", log_id="dGVzdDI=")
    db_session.add(source)
    await db_session.flush()

    httpx_mock.add_response(
        url=f"{source.url.rstrip('/')}{_STH_URL_SUFFIX}",
        json=_SAMPLE_STH,
        status_code=200,
    )
    async with httpx.AsyncClient() as client:
        state = await probe_log(source, client, db_session)

    # Verify via a fresh DB query to avoid stale session-cache values.
    await db_session.flush()
    await db_session.refresh(state)
    assert state.health_status == "ok"
    assert state.consecutive_failures == 0


# ---------------------------------------------------------------------------
# Failed probe
# ---------------------------------------------------------------------------


async def test_probe_log_http_error_sets_health_error(
    db_session: AsyncSession,
    httpx_mock: HTTPXMock,
) -> None:
    """HTTP 503 sets health_status='error' and stores the error message."""
    source = _make_log_source(url="https://ct3.example.com/log/", log_id="dGVzdDM=")
    db_session.add(source)
    await db_session.flush()

    httpx_mock.add_response(
        url=f"{source.url.rstrip('/')}{_STH_URL_SUFFIX}",
        status_code=503,
    )
    async with httpx.AsyncClient() as client:
        state = await probe_log(source, client, db_session)

    assert state.health_status == "error"
    assert state.last_error_message is not None
    assert state.last_error_at is not None
    assert state.last_probe_at is not None


async def test_probe_log_idempotent_upsert(
    db_session: AsyncSession,
    httpx_mock: HTTPXMock,
) -> None:
    """Two consecutive probes update the same runtime state row."""
    source = _make_log_source(url="https://ct4.example.com/log/", log_id="dGVzdDQ=")
    db_session.add(source)
    await db_session.flush()

    sth_url = f"{source.url.rstrip('/')}{_STH_URL_SUFFIX}"
    httpx_mock.add_response(url=sth_url, json=_SAMPLE_STH, status_code=200)
    httpx_mock.add_response(url=sth_url, json=_SAMPLE_STH, status_code=200)

    async with httpx.AsyncClient() as client:
        state1 = await probe_log(source, client, db_session)
        state2 = await probe_log(source, client, db_session)

    # Both should reference the same runtime state row
    assert state1.log_source_id == state2.log_source_id
    assert state2.health_status == "ok"
