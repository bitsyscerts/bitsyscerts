"""Tests for ctpool.retry_after — parse_retry_after and clamp_retry_after."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from email.utils import format_datetime

import pytest

from ctpool.retry_after import clamp_retry_after, parse_retry_after


class TestParseRetryAfterDeltaSeconds:
    def test_valid_integer_returns_value(self) -> None:
        assert parse_retry_after("60") == 60

    def test_zero_returns_zero(self) -> None:
        assert parse_retry_after("0") == 0

    def test_large_value_returns_value(self) -> None:
        assert parse_retry_after("3600") == 3600

    def test_negative_integer_returns_none(self) -> None:
        assert parse_retry_after("-1") is None

    def test_float_string_returns_none(self) -> None:
        assert parse_retry_after("1.5") is None


class TestParseRetryAfterHttpDate:
    def test_future_date_returns_positive_seconds(self) -> None:
        future = datetime.now(UTC) + timedelta(seconds=120)
        header = format_datetime(future, usegmt=True)
        result = parse_retry_after(header)
        assert result is not None
        assert 110 <= result <= 130  # allow small clock skew

    def test_past_date_returns_zero(self) -> None:
        past = datetime.now(UTC) - timedelta(seconds=60)
        header = format_datetime(past, usegmt=True)
        result = parse_retry_after(header)
        assert result == 0

    def test_malformed_date_returns_none(self) -> None:
        assert parse_retry_after("not-a-date") is None


class TestParseRetryAfterEdgeCases:
    def test_none_input_returns_none(self) -> None:
        assert parse_retry_after(None) is None

    def test_empty_string_returns_none(self) -> None:
        assert parse_retry_after("") is None

    def test_whitespace_string_returns_none(self) -> None:
        assert parse_retry_after("   ") is None


class TestClampRetryAfter:
    def test_value_below_max_unchanged(self) -> None:
        assert clamp_retry_after(30, 3600) == 30

    def test_value_equal_to_max_unchanged(self) -> None:
        assert clamp_retry_after(3600, 3600) == 3600

    def test_value_above_max_clamped_to_max(self) -> None:
        assert clamp_retry_after(7200, 3600) == 3600

    def test_zero_value_returns_zero(self) -> None:
        assert clamp_retry_after(0, 3600) == 0

    @pytest.mark.parametrize(
        "seconds,max_s,expected",
        [
            (100, 200, 100),
            (300, 200, 200),
            (200, 200, 200),
        ],
    )
    def test_parametrized_clamp(self, seconds: int, max_s: int, expected: int) -> None:
        assert clamp_retry_after(seconds, max_s) == expected
