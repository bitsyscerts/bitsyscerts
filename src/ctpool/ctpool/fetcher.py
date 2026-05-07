"""Async CT log entry and Signed Tree Head fetcher.

Exports:
    fetch_entries — Fetch a batch of CT log entries by index range.
    fetch_sth     — Fetch the current Signed Tree Head from a CT log.
"""

from __future__ import annotations

import httpx

from ctpool.ct_api_schemas import CtEntriesResponse, SignedTreeHead
from ctpool.exceptions import FetchError, RateLimitError
from ctpool.retry_after import clamp_retry_after, parse_retry_after


async def fetch_entries(
    log_url: str,
    start: int,
    end: int,
    client: httpx.AsyncClient,
) -> CtEntriesResponse:
    """Fetch CT log entries in the half-open range ``[start, end)``.

    Args:
        log_url: Base URL of the CT log (e.g. ``"https://ct.example.com/log/"``).
        start:   First log index to fetch (inclusive).
        end:     Last log index to fetch (inclusive per CT API spec).
        client:  Shared :class:`httpx.AsyncClient`.

    Returns:
        Validated :class:`CtEntriesResponse` with the raw leaf entries.

    Raises:
        FetchError: On any HTTP error or response validation failure.
    """
    url = f"{log_url.rstrip('/')}/ct/v1/get-entries"
    params = {"start": start, "end": end}
    try:
        response = await client.get(url, params=params)
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 429:
            _retry = _extract_retry_after(exc.response)
            raise RateLimitError(
                f"HTTP 429 fetching entries from {log_url} indices {start}-{end}",
                retry_after_seconds=_retry,
            ) from exc
        raise FetchError(
            f"HTTP {exc.response.status_code} fetching entries from {log_url} "
            f"indices {start}-{end}"
        ) from exc
    except httpx.RequestError as exc:
        raise FetchError(
            f"Request error fetching entries from {log_url}: {exc}"
        ) from exc

    try:
        return CtEntriesResponse.model_validate(response.json())
    except Exception as exc:
        raise FetchError(f"Invalid entries response from {log_url}: {exc}") from exc


async def fetch_sth(
    log_url: str,
    client: httpx.AsyncClient,
) -> SignedTreeHead:
    """Fetch the current Signed Tree Head (STH) from a CT log.

    Args:
        log_url: Base URL of the CT log.
        client:  Shared :class:`httpx.AsyncClient`.

    Returns:
        Validated :class:`SignedTreeHead` from the log.

    Raises:
        FetchError: On any HTTP error or response validation failure.
    """
    url = f"{log_url.rstrip('/')}/ct/v1/get-sth"
    try:
        response = await client.get(url)
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 429:
            _retry = _extract_retry_after(exc.response)
            raise RateLimitError(
                f"HTTP 429 fetching STH from {log_url}",
                retry_after_seconds=_retry,
            ) from exc
        raise FetchError(
            f"HTTP {exc.response.status_code} fetching STH from {log_url}"
        ) from exc
    except httpx.RequestError as exc:
        raise FetchError(f"Request error fetching STH from {log_url}: {exc}") from exc

    try:
        return SignedTreeHead.model_validate(response.json())
    except Exception as exc:
        raise FetchError(f"Invalid STH response from {log_url}: {exc}") from exc


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _extract_retry_after(response: httpx.Response) -> int | None:
    """Extract and parse the ``Retry-After`` header from a 429 response.

    Clamped to a default of 3600 s maximum.  Callers with access to the full
    ``Settings`` object may apply a further clamp from config.
    """
    import logging

    _max_retry_after = 3600
    header = response.headers.get("retry-after")
    parsed = parse_retry_after(header)
    if parsed is None:
        return None
    clamped = clamp_retry_after(parsed, _max_retry_after)
    if clamped != parsed:
        logging.getLogger(__name__).warning(
            "Retry-After header value %d s exceeds maximum %d s; clamping.",
            parsed,
            _max_retry_after,
        )
    return clamped
