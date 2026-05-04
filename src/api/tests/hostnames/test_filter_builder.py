"""Tests for hostnames/filter_builder.py — verifies generated WHERE conditions."""

from __future__ import annotations

from certsapi.hostnames.filter_builder import build_where_clause
from certsapi.hostnames.query_parser import ParsedQuery, QueryStrategy


def _exact(value: str) -> ParsedQuery:
    return ParsedQuery(strategy=QueryStrategy.exact, value=value)


def _wildcard(value: str) -> ParsedQuery:
    return ParsedQuery(strategy=QueryStrategy.wildcard, value=value)


def _regex(value: str) -> ParsedQuery:
    return ParsedQuery(strategy=QueryStrategy.regex, value=value)


# Note: SQLAlchemy binds literal values as :param_N in rendered SQL.
# Tests therefore assert on column names and SQL operators, not literal values.


class TestExactStrategy:
    def test_non_recursive_returns_one_equality_condition(self) -> None:
        conds = build_where_clause(_exact("api.example.com"), False, None)
        assert len(conds) == 1
        assert "hostname" in str(conds[0])

    def test_non_recursive_uses_equality_operator(self) -> None:
        conds = build_where_clause(_exact("api.example.com"), False, None)
        assert "=" in str(conds[0])
        assert "LIKE" not in str(conds[0])

    def test_recursive_no_depth_returns_registrable_domain_condition(self) -> None:
        conds = build_where_clause(_exact("example.com"), True, None)
        # registrable_domain equality + hostname != value (exclude root)
        assert len(conds) == 2
        assert any("registrable_domain" in str(c) for c in conds)

    def test_recursive_no_depth_excludes_root_domain(self) -> None:
        conds = build_where_clause(_exact("example.com"), True, None)
        sql_strs = [str(c) for c in conds]
        # The != condition uses != operator; LIKE is NOT present without a depth
        assert any("!=" in s for s in sql_strs)
        assert not any("LIKE" in s for s in sql_strs)

    def test_recursive_with_depth_adds_like_conditions(self) -> None:
        conds = build_where_clause(_exact("example.com"), True, 1)
        # registrable_domain + LIKE + NOT LIKE (depth LIKE already excludes root)
        assert len(conds) == 3

    def test_depth_without_recursive_is_ignored(self) -> None:
        conds = build_where_clause(_exact("api.example.com"), False, 2)
        assert len(conds) == 1

    def test_depth_1_generates_like_and_not_like(self) -> None:
        conds = build_where_clause(_exact("example.com"), True, 1)
        sql_strs = [str(c) for c in conds]
        assert any("LIKE" in s and "NOT" not in s for s in sql_strs)
        assert any("NOT LIKE" in s for s in sql_strs)

    def test_depth_2_generates_like_and_not_like(self) -> None:
        conds = build_where_clause(_exact("example.com"), True, 2)
        sql_strs = [str(c) for c in conds]
        assert any("LIKE" in s and "NOT" not in s for s in sql_strs)
        assert any("NOT LIKE" in s for s in sql_strs)


class TestWildcardStrategy:
    def test_returns_two_conditions(self) -> None:
        conds = build_where_clause(_wildcard("example.com"), False, None)
        assert len(conds) == 2

    def test_first_condition_is_like(self) -> None:
        conds = build_where_clause(_wildcard("example.com"), False, None)
        assert "LIKE" in str(conds[0])
        assert "NOT" not in str(conds[0])

    def test_second_condition_is_not_like(self) -> None:
        conds = build_where_clause(_wildcard("example.com"), False, None)
        assert "NOT LIKE" in str(conds[1])

    def test_wildcard_with_recursive_redirects_to_domain_search(self) -> None:
        # *.example.com + recursive=True must behave like example.com + recursive
        wildcard_conds = build_where_clause(_wildcard("example.com"), True, None)
        exact_conds = build_where_clause(_exact("example.com"), True, None)
        assert len(wildcard_conds) == len(exact_conds)
        assert all("LIKE" not in str(c) for c in wildcard_conds)

    def test_wildcard_with_recursive_and_depth_uses_depth_conditions(self) -> None:
        wildcard_conds = build_where_clause(_wildcard("example.com"), True, 2)
        exact_conds = build_where_clause(_exact("example.com"), True, 2)
        assert len(wildcard_conds) == len(exact_conds)
        assert any("LIKE" in str(c) for c in wildcard_conds)


class TestRegexStrategy:
    def test_returns_one_tilde_condition(self) -> None:
        conds = build_where_clause(_regex("^api\\."), False, None)
        assert len(conds) == 1
        assert "~" in str(conds[0])

    def test_pattern_column_is_hostname(self) -> None:
        conds = build_where_clause(_regex("test"), False, None)
        assert "hostname" in str(conds[0])
