"""Tests for ctpool.log_discovery — fetch_log_list and sync_log_sources.

fetch_log_list tests use pytest-httpx to intercept HTTP calls.
sync_log_sources tests use the real ``ctpool_test`` DB via ``db_session``.
"""

from __future__ import annotations

import httpx
import pytest
from pytest_httpx import HTTPXMock
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ctpool.ct_api_schemas import (
    CtLogInfo,
    CtLogListResponse,
    CtLogOperator,
    CtLogTemporalInterval,
)
from ctpool.exceptions import FetchError
from ctpool.log_discovery import fetch_log_list, sync_log_sources
from ctpool.models.log_source import CtLogSource

pytestmark = pytest.mark.integration

_LOG_LIST_URL = "https://www.gstatic.com/ct/log_list/v3/log_list.json"

_SAMPLE_RESPONSE = {
    "version": "3.0",
    "log_list_timestamp": "2024-01-01T00:00:00Z",
    "operators": [
        {
            "name": "Google",
            "email": ["ct@google.com"],
            "logs": [
                {
                    "description": "Google Xenon2024",
                    "log_id": "abc123==",
                    "key": "publickey==",
                    "url": "https://ct.googleapis.com/logs/xenon2024/",
                    "mmd": 86400,
                    "state": {"usable": {"timestamp": "2023-01-01T00:00:00Z"}},
                    "temporal_interval": {
                        "start_inclusive": "2024-01-01T00:00:00Z",
                        "end_exclusive": "2025-01-01T00:00:00Z",
                    },
                }
            ],
        }
    ],
}


# ---------------------------------------------------------------------------
# fetch_log_list
# ---------------------------------------------------------------------------


async def test_fetch_log_list_success(httpx_mock: HTTPXMock) -> None:
    """fetch_log_list returns a valid CtLogListResponse on 200."""
    httpx_mock.add_response(
        url=_LOG_LIST_URL,
        json=_SAMPLE_RESPONSE,
        status_code=200,
    )
    async with httpx.AsyncClient() as client:
        result = await fetch_log_list(client)

    assert isinstance(result, CtLogListResponse)
    assert len(result.operators) == 1
    assert result.operators[0].name == "Google"
    assert len(result.operators[0].logs) == 1


async def test_fetch_log_list_http_error_raises_fetch_error(
    httpx_mock: HTTPXMock,
) -> None:
    """HTTP 500 raises FetchError."""
    httpx_mock.add_response(url=_LOG_LIST_URL, status_code=500)
    async with httpx.AsyncClient() as client:
        with pytest.raises(FetchError, match="HTTP 500"):
            await fetch_log_list(client)


async def test_fetch_log_list_invalid_json_raises_fetch_error(
    httpx_mock: HTTPXMock,
) -> None:
    """Non-JSON response raises FetchError."""
    httpx_mock.add_response(
        url=_LOG_LIST_URL,
        content=b"not json",
        status_code=200,
    )
    async with httpx.AsyncClient() as client:
        with pytest.raises(FetchError):
            await fetch_log_list(client)


async def test_fetch_log_list_custom_url(httpx_mock: HTTPXMock) -> None:
    """Custom URL is used instead of the default Chrome list URL."""
    custom_url = "https://example.com/log_list.json"
    httpx_mock.add_response(url=custom_url, json=_SAMPLE_RESPONSE, status_code=200)
    async with httpx.AsyncClient() as client:
        result = await fetch_log_list(client, url=custom_url)

    assert isinstance(result, CtLogListResponse)


# ---------------------------------------------------------------------------
# sync_log_sources
# ---------------------------------------------------------------------------


def _make_log_list(
    *,
    operator_name: str = "Test Op",
    log_id: str = "dGVzdA==",
    url: str = "https://ct.example.com/log/",
    state: dict[str, object] | None = None,
) -> CtLogListResponse:
    if state is None:
        state = {"usable": {"timestamp": "2023-01-01T00:00:00Z"}}
    return CtLogListResponse(
        operators=[
            CtLogOperator(
                name=operator_name,
                email=[],
                logs=[
                    CtLogInfo(
                        description="Test log",
                        log_id=log_id,
                        key="a2V5==",
                        url=url,
                        mmd=86400,
                        state=state,
                    )
                ],
            )
        ]
    )


async def test_sync_log_sources_inserts_rows(db_session: AsyncSession) -> None:
    """sync_log_sources upserts one row per log."""
    log_list = _make_log_list()
    upserted, operators = await sync_log_sources(db_session, log_list)
    await db_session.flush()

    assert upserted == 1
    assert operators == 1
    result = await db_session.execute(
        select(CtLogSource).where(CtLogSource.url == "https://ct.example.com/log/")
    )
    row = result.scalars().first()
    assert row is not None
    assert row.operator_name == "Test Op"
    assert row.is_eligible_for_tail is True


async def test_sync_log_sources_updates_on_conflict(db_session: AsyncSession) -> None:
    """Second call with same URL updates operator_name and log_state."""
    log_list = _make_log_list(
        operator_name="Old Op", url="https://ct2.example.com/log/"
    )
    await sync_log_sources(db_session, log_list)
    await db_session.flush()

    updated_list = _make_log_list(
        operator_name="New Op",
        url="https://ct2.example.com/log/",
        log_id="dGVzdA==",
    )
    await sync_log_sources(db_session, updated_list)
    await db_session.flush()

    result = await db_session.execute(
        select(CtLogSource).where(CtLogSource.url == "https://ct2.example.com/log/")
    )
    row = result.scalars().first()
    assert row is not None
    assert row.operator_name == "New Op"


async def test_sync_log_sources_non_usable_log_not_eligible(
    db_session: AsyncSession,
) -> None:
    """A log with state 'retired' is not eligible for tail or backfill."""
    log_list = _make_log_list(
        url="https://ct3.example.com/log/",
        log_id="dGVzdDM=",
        state={"retired": {"timestamp": "2023-01-01T00:00:00Z"}},
    )
    await sync_log_sources(db_session, log_list)
    await db_session.flush()

    result = await db_session.execute(
        select(CtLogSource).where(CtLogSource.url == "https://ct3.example.com/log/")
    )
    row = result.scalars().first()
    assert row is not None
    assert row.is_eligible_for_tail is False
    assert row.is_eligible_for_backfill is False


async def test_sync_log_sources_multiple_operators(db_session: AsyncSession) -> None:
    """Two operators produce two log rows."""
    log_list = CtLogListResponse(
        operators=[
            CtLogOperator(
                name="Op A",
                email=[],
                logs=[
                    CtLogInfo(
                        description="Log A",
                        log_id="AAAA==",
                        key="a2V5==",
                        url="https://cta.example.com/log/",
                        mmd=86400,
                        state={"usable": {}},
                    )
                ],
            ),
            CtLogOperator(
                name="Op B",
                email=[],
                logs=[
                    CtLogInfo(
                        description="Log B",
                        log_id="BBBB==",
                        key="a2V5==",
                        url="https://ctb.example.com/log/",
                        mmd=86400,
                        state={"usable": {}},
                    )
                ],
            ),
        ]
    )
    upserted, operators = await sync_log_sources(db_session, log_list)
    assert upserted == 2
    assert operators == 2


async def test_fetch_log_list_request_error_raises_fetch_error(
    httpx_mock: HTTPXMock,
) -> None:
    """Network error raises FetchError."""
    httpx_mock.add_exception(httpx.ConnectError("connection refused"))
    async with httpx.AsyncClient() as client:
        with pytest.raises(FetchError, match="Request error"):
            await fetch_log_list(client)


async def test_sync_log_sources_with_temporal_interval(
    db_session: AsyncSession,
) -> None:
    """Temporal shard dates are parsed and stored when present."""
    log_list = CtLogListResponse(
        operators=[
            CtLogOperator(
                name="Op Shard",
                email=[],
                logs=[
                    CtLogInfo(
                        description="Shard Log",
                        log_id="c2hhcmQ=",
                        key="a2V5==",
                        url="https://shard.example.com/log/",
                        mmd=86400,
                        state={"usable": {}},
                        temporal_interval=CtLogTemporalInterval(
                            start_inclusive="2024-01-01T00:00:00Z",
                            end_exclusive="2025-01-01T00:00:00Z",
                        ),
                    )
                ],
            )
        ]
    )
    await sync_log_sources(db_session, log_list)
    await db_session.flush()

    result = await db_session.execute(
        select(CtLogSource).where(CtLogSource.url == "https://shard.example.com/log/")
    )
    row = result.scalars().first()
    assert row is not None
    assert row.temporal_shard_start is not None
    assert row.temporal_shard_end is not None


async def test_sync_log_sources_no_state_stores_unknown(
    db_session: AsyncSession,
) -> None:
    """A log with state=None stores log_state='unknown'."""
    log_list = CtLogListResponse(
        operators=[
            CtLogOperator(
                name="Op Unknown",
                email=[],
                logs=[
                    CtLogInfo(
                        description="Unknown Log",
                        log_id="dW5r",
                        key="a2V5==",
                        url="https://unknown.example.com/log/",
                        mmd=86400,
                        state=None,
                    )
                ],
            )
        ]
    )
    await sync_log_sources(db_session, log_list)
    await db_session.flush()

    result = await db_session.execute(
        select(CtLogSource).where(CtLogSource.url == "https://unknown.example.com/log/")
    )
    row = result.scalars().first()
    assert row is not None
    assert row.log_state == "unknown"
    assert row.is_eligible_for_tail is False
