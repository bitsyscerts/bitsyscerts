"""Domain-specific exceptions for the hostnames search endpoint."""

from __future__ import annotations

from certsapi.exceptions import BitsyApiError


class InvalidCursorError(BitsyApiError):
    """Raised when a pagination cursor cannot be decoded or is stale."""


class InvalidQueryError(BitsyApiError):
    """Raised when the search query string is malformed or invalid."""
