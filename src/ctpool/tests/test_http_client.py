"""Tests for ctpool.http_client — build_httpx_client."""

from __future__ import annotations

import httpx

from ctpool.config import Settings
from ctpool.http_client import build_httpx_client


def test_build_httpx_client_returns_async_client(test_settings: Settings) -> None:
    """build_httpx_client returns an httpx.AsyncClient."""
    client = build_httpx_client(test_settings)
    assert isinstance(client, httpx.AsyncClient)


def test_build_httpx_client_timeout_matches_settings(test_settings: Settings) -> None:
    """The client timeout equals ct_http_timeout_seconds from settings."""
    client = build_httpx_client(test_settings)
    assert client.timeout.read == test_settings.ct_http_timeout_seconds


def test_build_httpx_client_has_accept_json_header(test_settings: Settings) -> None:
    """The client has an Accept: application/json header set."""
    client = build_httpx_client(test_settings)
    assert client.headers.get("accept") == "application/json"


def test_build_httpx_client_follows_redirects(test_settings: Settings) -> None:
    """The client is configured to follow redirects."""
    client = build_httpx_client(test_settings)
    assert client.follow_redirects is True
