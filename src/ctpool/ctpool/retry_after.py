"""Parse and clamp ``Retry-After`` header values for HTTP 429 responses.

Exports:
    parse_retry_after  — Parse a raw Retry-After string into seconds.
    clamp_retry_after  — Clamp a parsed value against a configured maximum.
"""

from __future__ import annotations

from datetime import UTC, datetime
from email.utils import parsedate_to_datetime


def parse_retry_after(header_value: str | None) -> int | None:
    """Parse a raw ``Retry-After`` header string into an integer number of seconds.

    Supports two RFC 7231 formats:
      - Delta-seconds:  ``"60"``
      - HTTP-date:      ``"Wed, 21 Oct 2015 07:28:00 GMT"``

    Args:
        header_value: Raw header value string, or ``None`` if the header was absent.

    Returns:
        Integer seconds to wait, or ``None`` if the header is absent or unparseable.
        Returns ``0`` if the parsed HTTP-date is in the past.
    """
    if header_value is None:
        return None
    stripped = header_value.strip()
    if _is_delta_seconds(stripped):
        return _parse_delta_seconds(stripped)
    return _parse_http_date(stripped)


def clamp_retry_after(seconds: int, max_seconds: int) -> int:
    """Clamp *seconds* to at most *max_seconds*.

    Args:
        seconds:     Parsed retry delay in seconds (must be >= 0).
        max_seconds: Maximum allowed value (must be > 0).

    Returns:
        The clamped value: ``min(seconds, max_seconds)``.
    """
    return min(seconds, max_seconds)


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _is_delta_seconds(value: str) -> bool:
    """Return True if *value* looks like a non-negative integer string."""
    return value.isdigit()


def _parse_delta_seconds(value: str) -> int | None:
    """Parse a delta-seconds string; return None if negative or invalid."""
    try:
        n = int(value)
    except ValueError:
        return None
    return max(0, n)


def _parse_http_date(value: str) -> int | None:
    """Parse an HTTP-date string and return seconds until that time.

    Returns ``0`` if the date is in the past.  Returns ``None`` on any parse
    failure.
    """
    try:
        parsed = parsedate_to_datetime(value)
    except Exception:  # noqa: BLE001
        return None
    now = datetime.now(UTC)
    delta = (parsed - now).total_seconds()
    return max(0, int(delta))
