"""Async HTTP client construction for CT log API requests.

Exports:
    build_httpx_client — Return a configured httpx.AsyncClient.
"""

from __future__ import annotations

import httpx

from ctpool.config import Settings


def build_httpx_client(settings: Settings) -> httpx.AsyncClient:
    """Return a configured :class:`httpx.AsyncClient` for CT log requests.

    The client uses a ``Retry-After``-aware timeout derived from settings and
    sets appropriate headers for public CT log APIs.

    Args:
        settings: Application settings containing timeout configuration.

    Returns:
        A new :class:`httpx.AsyncClient` that the caller must close.
    """
    return httpx.AsyncClient(
        timeout=httpx.Timeout(settings.ct_http_timeout_seconds),
        headers={"Accept": "application/json"},
        follow_redirects=True,
    )
