"""Tests for ctpool.fetcher — fetch_entries and fetch_sth."""

from __future__ import annotations

import httpx
import pytest
from pytest_httpx import HTTPXMock

from ctpool.config import Settings
from ctpool.ct_api_schemas import CtEntriesResponse, SignedTreeHead
from ctpool.exceptions import FetchError, RateLimitError
from ctpool.fetcher import fetch_entries, fetch_sth
from ctpool.http_client import build_httpx_client

_LOG_URL = "https://ct.example.com/log"

_STH_PAYLOAD = {
    "tree_size": 12345,
    "timestamp": 1700000000000,
    "sha256_root_hash": "abc123==",
    "tree_head_signature": "sig==",
}

_ENTRIES_PAYLOAD = {
    "entries": [
        {"leaf_input": "AAAA", "extra_data": "BBBB"},
        {"leaf_input": "CCCC", "extra_data": "DDDD"},
    ]
}


# ---------------------------------------------------------------------------
# fetch_sth
# ---------------------------------------------------------------------------


async def test_fetch_sth_returns_signed_tree_head(
    test_settings: Settings,
    httpx_mock: HTTPXMock,
) -> None:
    """fetch_sth returns a validated SignedTreeHead on HTTP 200."""
    httpx_mock.add_response(
        url=f"{_LOG_URL}/ct/v1/get-sth",
        json=_STH_PAYLOAD,
    )
    async with build_httpx_client(test_settings) as client:
        sth = await fetch_sth(_LOG_URL, client)
    assert isinstance(sth, SignedTreeHead)
    assert sth.tree_size == 12345


async def test_fetch_sth_raises_fetch_error_on_4xx(
    test_settings: Settings,
    httpx_mock: HTTPXMock,
) -> None:
    """fetch_sth raises RateLimitError on HTTP 429."""
    httpx_mock.add_response(
        url=f"{_LOG_URL}/ct/v1/get-sth",
        status_code=429,
    )
    async with build_httpx_client(test_settings) as client:
        with pytest.raises(RateLimitError, match="HTTP 429"):
            await fetch_sth(_LOG_URL, client)


async def test_fetch_sth_raises_fetch_error_on_5xx(
    test_settings: Settings,
    httpx_mock: HTTPXMock,
) -> None:
    """fetch_sth raises FetchError on HTTP 503."""
    httpx_mock.add_response(
        url=f"{_LOG_URL}/ct/v1/get-sth",
        status_code=503,
    )
    async with build_httpx_client(test_settings) as client:
        with pytest.raises(FetchError, match="HTTP 503"):
            await fetch_sth(_LOG_URL, client)


async def test_fetch_sth_raises_fetch_error_on_invalid_json(
    test_settings: Settings,
    httpx_mock: HTTPXMock,
) -> None:
    """fetch_sth raises FetchError when response body fails Pydantic validation."""
    httpx_mock.add_response(
        url=f"{_LOG_URL}/ct/v1/get-sth",
        json={"unexpected_field": True},
    )
    async with build_httpx_client(test_settings) as client:
        with pytest.raises(FetchError, match="Invalid STH response"):
            await fetch_sth(_LOG_URL, client)


async def test_fetch_sth_strips_trailing_slash_from_url(
    test_settings: Settings,
    httpx_mock: HTTPXMock,
) -> None:
    """fetch_sth tolerates a trailing slash in log_url."""
    httpx_mock.add_response(
        url=f"{_LOG_URL}/ct/v1/get-sth",
        json=_STH_PAYLOAD,
    )
    async with build_httpx_client(test_settings) as client:
        sth = await fetch_sth(_LOG_URL + "/", client)
    assert sth.tree_size == 12345


# ---------------------------------------------------------------------------
# fetch_entries
# ---------------------------------------------------------------------------


async def test_fetch_entries_returns_ct_entries_response(
    test_settings: Settings,
    httpx_mock: HTTPXMock,
) -> None:
    """fetch_entries returns a validated CtEntriesResponse on HTTP 200."""
    httpx_mock.add_response(
        url=f"{_LOG_URL}/ct/v1/get-entries?start=0&end=9",
        json=_ENTRIES_PAYLOAD,
    )
    async with build_httpx_client(test_settings) as client:
        resp = await fetch_entries(_LOG_URL, 0, 9, client)
    assert isinstance(resp, CtEntriesResponse)
    assert len(resp.entries) == 2


async def test_fetch_entries_raises_fetch_error_on_4xx(
    test_settings: Settings,
    httpx_mock: HTTPXMock,
) -> None:
    """fetch_entries raises FetchError on HTTP 400."""
    httpx_mock.add_response(
        url=f"{_LOG_URL}/ct/v1/get-entries?start=0&end=9",
        status_code=400,
    )
    async with build_httpx_client(test_settings) as client:
        with pytest.raises(FetchError, match="HTTP 400"):
            await fetch_entries(_LOG_URL, 0, 9, client)


async def test_fetch_entries_raises_fetch_error_on_invalid_payload(
    test_settings: Settings,
    httpx_mock: HTTPXMock,
) -> None:
    """fetch_entries raises FetchError when the response does not match schema."""
    httpx_mock.add_response(
        url=f"{_LOG_URL}/ct/v1/get-entries?start=5&end=10",
        json={"bad": "data"},
    )
    async with build_httpx_client(test_settings) as client:
        with pytest.raises(FetchError, match="Invalid entries response"):
            await fetch_entries(_LOG_URL, 5, 10, client)


async def test_fetch_entries_sends_start_end_params(
    test_settings: Settings,
    httpx_mock: HTTPXMock,
) -> None:
    """fetch_entries sends start and end as query parameters."""
    httpx_mock.add_response(
        url=f"{_LOG_URL}/ct/v1/get-entries?start=100&end=199",
        json=_ENTRIES_PAYLOAD,
    )
    async with build_httpx_client(test_settings) as client:
        resp = await fetch_entries(_LOG_URL, 100, 199, client)
    assert len(resp.entries) == 2


async def test_fetch_sth_raises_fetch_error_on_connect_error(
    test_settings: Settings,
    httpx_mock: HTTPXMock,
) -> None:
    """fetch_sth raises FetchError on httpx.ConnectError (RequestError subclass)."""
    httpx_mock.add_exception(
        httpx.ConnectError("connection refused"),
        url=f"{_LOG_URL}/ct/v1/get-sth",
    )
    async with build_httpx_client(test_settings) as client:
        with pytest.raises(FetchError, match="Request error"):
            await fetch_sth(_LOG_URL, client)


async def test_fetch_entries_raises_fetch_error_on_connect_error(
    test_settings: Settings,
    httpx_mock: HTTPXMock,
) -> None:
    """fetch_entries raises FetchError on httpx.ConnectError (RequestError subclass)."""
    httpx_mock.add_exception(
        httpx.ConnectError("connection refused"),
        url=f"{_LOG_URL}/ct/v1/get-entries?start=0&end=9",
    )
    async with build_httpx_client(test_settings) as client:
        with pytest.raises(FetchError, match="Request error"):
            await fetch_entries(_LOG_URL, 0, 9, client)
