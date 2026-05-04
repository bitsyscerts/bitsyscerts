"""Opaque base64url pagination cursor for keyset-paginated hostname search."""

from __future__ import annotations

import base64
import binascii
import json
from dataclasses import dataclass

from certsapi.hostnames.exceptions import InvalidCursorError


@dataclass(frozen=True, slots=True)
class PageCursor:
    """Encodes the position of the last seen row in a keyset-paginated result."""

    sort: str
    timestamp_ms: int
    id_uuid: str


def encode_cursor(cursor: PageCursor) -> str:
    """Serialize *cursor* to an opaque base64url string."""
    payload = json.dumps(
        {"sort": cursor.sort, "ts_ms": cursor.timestamp_ms, "id": cursor.id_uuid},
        separators=(",", ":"),
    ).encode()
    return base64.urlsafe_b64encode(payload).decode()


def decode_cursor(raw: str) -> PageCursor:
    """Deserialize *raw* base64url string back to a PageCursor.

    Raises:
        InvalidCursorError: If *raw* is not valid base64url, not valid JSON,
            or is missing required fields.
    """
    try:
        padded = raw + "=" * (-len(raw) % 4)
        data = json.loads(base64.urlsafe_b64decode(padded))
        return PageCursor(
            sort=str(data["sort"]),
            timestamp_ms=int(data["ts_ms"]),
            id_uuid=str(data["id"]),
        )
    except (KeyError, ValueError, TypeError, binascii.Error) as exc:
        raise InvalidCursorError(f"Malformed pagination cursor: {exc}") from exc
