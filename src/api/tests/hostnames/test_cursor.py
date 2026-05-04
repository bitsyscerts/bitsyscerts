"""Tests for hostnames/cursor.py: encode/decode round-trips and error cases."""

from __future__ import annotations

import base64
import json

import pytest

from certsapi.hostnames.cursor import PageCursor, decode_cursor, encode_cursor
from certsapi.hostnames.exceptions import InvalidCursorError


def _make_cursor(
    sort: str = "not_before_desc",
    timestamp_ms: int = 1_700_000_000_000,
    id_uuid: str = "00000000-0000-0000-0000-000000000001",
) -> PageCursor:
    return PageCursor(sort=sort, timestamp_ms=timestamp_ms, id_uuid=id_uuid)


class TestEncodeDecode:
    def test_round_trip_preserves_all_fields(self) -> None:
        original = _make_cursor()
        assert decode_cursor(encode_cursor(original)) == original

    def test_sort_field_preserved(self) -> None:
        cursor = _make_cursor(sort="not_after_asc")
        assert decode_cursor(encode_cursor(cursor)).sort == "not_after_asc"

    def test_timestamp_ms_preserved(self) -> None:
        cursor = _make_cursor(timestamp_ms=1_234_567_890_123)
        assert decode_cursor(encode_cursor(cursor)).timestamp_ms == 1_234_567_890_123

    def test_id_uuid_preserved(self) -> None:
        uid = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
        cursor = _make_cursor(id_uuid=uid)
        assert decode_cursor(encode_cursor(cursor)).id_uuid == uid

    def test_min_timestamp_boundary(self) -> None:
        cursor = _make_cursor(timestamp_ms=0)
        assert decode_cursor(encode_cursor(cursor)).timestamp_ms == 0

    def test_max_timestamp_boundary(self) -> None:
        large = 9_999_999_999_999
        cursor = _make_cursor(timestamp_ms=large)
        assert decode_cursor(encode_cursor(cursor)).timestamp_ms == large


class TestDecodeErrors:
    def test_corrupt_base64_raises(self) -> None:
        with pytest.raises(InvalidCursorError):
            decode_cursor("!!!not-valid-base64!!!")

    def test_valid_base64_but_not_json_raises(self) -> None:
        raw = base64.urlsafe_b64encode(b"not json").decode()
        with pytest.raises(InvalidCursorError):
            decode_cursor(raw)

    def test_valid_json_missing_sort_key_raises(self) -> None:
        data = json.dumps({"ts_ms": 123, "id": "abc"}).encode()
        raw = base64.urlsafe_b64encode(data).decode()
        with pytest.raises(InvalidCursorError):
            decode_cursor(raw)

    def test_valid_json_missing_ts_ms_raises(self) -> None:
        data = json.dumps({"sort": "not_before_desc", "id": "abc"}).encode()
        raw = base64.urlsafe_b64encode(data).decode()
        with pytest.raises(InvalidCursorError):
            decode_cursor(raw)

    def test_valid_json_missing_id_raises(self) -> None:
        data = json.dumps({"sort": "not_before_desc", "ts_ms": 123}).encode()
        raw = base64.urlsafe_b64encode(data).decode()
        with pytest.raises(InvalidCursorError):
            decode_cursor(raw)

    def test_empty_string_raises(self) -> None:
        with pytest.raises(InvalidCursorError):
            decode_cursor("")
