"""Hostname search service: orchestrates parse → validate → fetch → paginate."""

from __future__ import annotations

from certsapi.hostnames.cursor import PageCursor, decode_cursor, encode_cursor
from certsapi.hostnames.exceptions import InvalidCursorError
from certsapi.hostnames.models import (
    HostnameListResponse,
    HostnameResult,
    HostnameSearchParams,
    SortField,
)
from certsapi.hostnames.query_parser import parse_query
from certsapi.hostnames.repository import HostnameRepository


def _validate_cursor(raw: str, sort: SortField) -> PageCursor:
    """Decode and validate cursor sort field matches the current request sort."""
    cursor = decode_cursor(raw)
    if cursor.sort != sort.value:
        raise InvalidCursorError(
            f"Cursor sort '{cursor.sort}' does not match requested sort '{sort.value}'"
        )
    return cursor


def _make_next_cursor(last: HostnameResult, sort: SortField) -> str | None:
    """Encode the next-page cursor from the last result row, or None if no ts."""
    ts = (
        last.latest_cert_not_before
        if sort.value.startswith("not_before")
        else last.latest_cert_not_after
    )
    if ts is None:
        return None
    return encode_cursor(
        PageCursor(
            sort=sort.value,
            timestamp_ms=int(ts.timestamp() * 1000),
            id_uuid=str(last.id),
        )
    )


def _build_response(
    rows: list[HostnameResult],
    sort: SortField,
    limit: int,
    total_estimate: int | None = None,
) -> HostnameListResponse:
    """Slice rows to limit, compute next_cursor, and build the list response."""
    has_next = len(rows) > limit
    items = rows[:limit]
    next_cursor = _make_next_cursor(items[-1], sort) if has_next and items else None
    return HostnameListResponse(
        items=items,
        next_cursor=next_cursor,
        total_returned=len(items),
        total_estimate=total_estimate,
    )


class HostnameService:
    """Orchestrates query parsing, cursor validation, DB fetch, and pagination."""

    def __init__(self, repository: HostnameRepository) -> None:
        self._repository = repository

    async def search(self, params: HostnameSearchParams) -> HostnameListResponse:
        """Parse the query, validate any cursor, fetch results, and paginate."""
        parsed = parse_query(params.q)
        cursor = _validate_cursor(params.cursor, params.sort) if params.cursor else None
        rows = await self._repository.search(parsed, params, cursor)
        estimate = (
            await self._repository.count_estimate(parsed, params)
            if cursor is None
            else None
        )
        return _build_response(rows, params.sort, params.limit, estimate)
