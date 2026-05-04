"""Tests for hostnames/query_parser.py."""

from __future__ import annotations

import pytest

from certsapi.hostnames.exceptions import InvalidQueryError
from certsapi.hostnames.query_parser import QueryStrategy, parse_query


class TestExactStrategy:
    def test_plain_fqdn_returns_exact(self) -> None:
        result = parse_query("api.example.com")
        assert result.strategy == QueryStrategy.exact
        assert result.value == "api.example.com"

    def test_single_label_returns_exact(self) -> None:
        result = parse_query("localhost")
        assert result.strategy == QueryStrategy.exact
        assert result.value == "localhost"


class TestWildcardStrategy:
    def test_wildcard_prefix_detected(self) -> None:
        result = parse_query("*.example.com")
        assert result.strategy == QueryStrategy.wildcard
        assert result.value == "example.com"

    def test_wildcard_strips_prefix(self) -> None:
        result = parse_query("*.sub.example.com")
        assert result.value == "sub.example.com"

    def test_wildcard_no_domain_raises(self) -> None:
        with pytest.raises(InvalidQueryError, match="must include a domain"):
            parse_query("*.")

    def test_multiple_wildcards_raises(self) -> None:
        with pytest.raises(InvalidQueryError, match="Only one wildcard"):
            parse_query("*.*.example.com")


class TestRegexStrategy:
    def test_re_prefix_detected(self) -> None:
        result = parse_query("re:^api\\.")
        assert result.strategy == QueryStrategy.regex
        assert result.value == "^api\\."

    def test_re_prefix_strips_marker(self) -> None:
        result = parse_query("re:.*\\.example\\.com$")
        assert result.value == ".*\\.example\\.com$"

    def test_invalid_regex_raises(self) -> None:
        with pytest.raises(InvalidQueryError, match="Invalid regex"):
            parse_query("re:[unclosed")

    def test_empty_pattern_after_prefix_raises(self) -> None:
        with pytest.raises(InvalidQueryError, match="must not be empty"):
            parse_query("re:")


class TestInputValidation:
    def test_empty_string_raises(self) -> None:
        with pytest.raises(InvalidQueryError, match="must not be empty"):
            parse_query("")

    def test_whitespace_only_raises(self) -> None:
        with pytest.raises(InvalidQueryError, match="must not be empty"):
            parse_query("   ")
