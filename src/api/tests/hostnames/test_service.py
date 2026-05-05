"""Tests for HostnameService — mocked repository, pure business-logic coverage."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from certsapi.hostnames.exceptions import InvalidCursorError, InvalidQueryError
from certsapi.hostnames.models import (
    HostnameListResponse,
    HostnameResult,
    HostnameSearchParams,
    SortField,
)
from certsapi.hostnames.service import HostnameService


def _make_result(
    hostname: str = "api.example.com",
    not_before: datetime | None = None,
) -> HostnameResult:
    ts = not_before or datetime(2024, 6, 1, tzinfo=UTC)
    return HostnameResult(
        id=uuid.uuid4(),
        hostname=hostname,
        registrable_domain="example.com",
        is_wildcard=False,
        first_seen_ct=None,
        last_seen_ct=None,
        latest_cert_not_before=ts,
        latest_cert_not_after=ts,
        latest_cert=None,
    )


def _params(**kwargs: object) -> HostnameSearchParams:
    defaults: dict[str, object] = {"q": "api.example.com", "limit": 50}
    defaults.update(kwargs)
    return HostnameSearchParams(**defaults)  # type: ignore[arg-type]


class TestHostnameServiceSearch:
    async def test_happy_path_returns_list_response(self) -> None:
        repo = AsyncMock()
        repo.search.return_value = [_make_result()]
        repo.count_estimate.return_value = 1
        service = HostnameService(repo)

        result = await service.search(_params())

        assert isinstance(result, HostnameListResponse)
        assert result.total_returned == 1
        assert result.next_cursor is None

    async def test_invalid_q_raises_invalid_query_error(self) -> None:
        repo = AsyncMock()
        service = HostnameService(repo)
        with pytest.raises(InvalidQueryError):
            await service.search(_params(q=""))

    async def test_cursor_generated_when_rows_exceed_limit(self) -> None:
        limit = 2
        rows = [_make_result(f"h{i}.example.com") for i in range(limit + 1)]
        repo = AsyncMock()
        repo.search.return_value = rows
        repo.count_estimate.return_value = 3
        service = HostnameService(repo)

        result = await service.search(_params(limit=limit))

        assert result.next_cursor is not None
        assert result.total_returned == limit

    async def test_no_cursor_when_rows_at_or_below_limit(self) -> None:
        repo = AsyncMock()
        repo.search.return_value = [_make_result()]
        repo.count_estimate.return_value = 1
        service = HostnameService(repo)

        result = await service.search(_params(limit=50))

        assert result.next_cursor is None

    async def test_stale_cursor_sort_raises_invalid_cursor_error(self) -> None:
        from certsapi.hostnames.cursor import PageCursor, encode_cursor

        cursor = encode_cursor(
            PageCursor(
                sort="not_before_asc",
                timestamp_ms=1_700_000_000_000,
                id_uuid=str(uuid.uuid4()),
            )
        )
        repo = AsyncMock()
        service = HostnameService(repo)

        with pytest.raises(InvalidCursorError):
            await service.search(_params(cursor=cursor, sort=SortField.not_before_desc))

    async def test_malformed_cursor_raises_invalid_cursor_error(self) -> None:
        repo = AsyncMock()
        service = HostnameService(repo)
        with pytest.raises(InvalidCursorError):
            await service.search(_params(cursor="not-a-valid-cursor"))

    async def test_no_cursor_when_last_row_has_null_timestamp(self) -> None:
        limit = 1
        row = HostnameResult(
            id=uuid.uuid4(),
            hostname="api.example.com",
            registrable_domain="example.com",
            is_wildcard=False,
            first_seen_ct=None,
            last_seen_ct=None,
            latest_cert_not_before=None,
            latest_cert_not_after=None,
            latest_cert=None,
        )
        repo = AsyncMock()
        repo.search.return_value = [row, row]  # limit+1 rows but null timestamps
        repo.count_estimate.return_value = 2
        service = HostnameService(repo)

        result = await service.search(_params(limit=limit))

        assert result.next_cursor is None

    async def test_total_estimate_present_on_first_page(self) -> None:
        repo = AsyncMock()
        repo.search.return_value = [_make_result()]
        repo.count_estimate.return_value = 42_000
        service = HostnameService(repo)

        result = await service.search(_params())

        assert result.total_estimate == 42_000
        repo.count_estimate.assert_awaited_once()

    async def test_total_estimate_absent_on_subsequent_pages(self) -> None:
        from certsapi.hostnames.cursor import PageCursor, encode_cursor

        cursor = encode_cursor(
            PageCursor(
                sort="not_before_desc",
                timestamp_ms=1_700_000_000_000,
                id_uuid=str(uuid.uuid4()),
            )
        )
        repo = AsyncMock()
        repo.search.return_value = [_make_result()]
        service = HostnameService(repo)

        result = await service.search(_params(cursor=cursor))

        assert result.total_estimate is None
        repo.count_estimate.assert_not_awaited()
