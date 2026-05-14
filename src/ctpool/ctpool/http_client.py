"""Async HTTP client construction for CT log API requests.

Exports:
    build_httpx_client — Return a configured httpx.AsyncClient.
"""

from __future__ import annotations

import socket

import httpx

from ctpool import __version__
from ctpool.config import Settings


def _build_user_agent(settings: Settings) -> str:
    """Build a descriptive User-Agent string for this deployment.

    Format::

        bitsyscerts-ctpool/<version> (<fqdn>; +<repo>; <contact>)

    The FQDN lets CT log operators identify which host is making requests.
    The optional contact field (``ct_operator_contact``) lets them reach the
    deployment operator directly when there is a problem.

    Args:
        settings: Application settings, used for the operator contact field.

    Returns:
        A User-Agent string safe for inclusion in HTTP headers.
    """
    fqdn = socket.getfqdn()
    parts = [
        fqdn,
        "+https://github.com/bitsyscerts/bitsyscerts",
    ]
    if settings.ct_operator_contact:
        parts.append(settings.ct_operator_contact)
    comment = "; ".join(parts)
    return f"bitsyscerts-ctpool/{__version__} ({comment})"


def build_httpx_client(settings: Settings) -> httpx.AsyncClient:
    """Return a configured :class:`httpx.AsyncClient` for CT log requests.

    The User-Agent identifies the software version, the host FQDN, and
    optionally the operator contact configured via ``CT_OPERATOR_CONTACT``.
    This lets CT log operators identify and reach the specific deployment
    responsible for unusual traffic.

    Args:
        settings: Application settings containing timeout and contact config.

    Returns:
        A new :class:`httpx.AsyncClient` that the caller must close.
    """
    return httpx.AsyncClient(
        timeout=httpx.Timeout(settings.ct_http_timeout_seconds),
        headers={
            "Accept": "application/json",
            "User-Agent": _build_user_agent(settings),
        },
        follow_redirects=True,
    )
