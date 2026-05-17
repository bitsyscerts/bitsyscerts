"""Tests for hostnames/filter_builder.py — verifies generated WHERE conditions."""

from __future__ import annotations

from sqlalchemy.dialects import postgresql

from certsapi.hostnames.filter_builder import build_where_clause
from certsapi.hostnames.query_parser import ParsedQuery, QueryStrategy


def _literal(clause: object) -> str:
    """Render a SQLAlchemy clause with literal bind values substituted in."""
    return str(
        clause.compile(  # type: ignore[union-attr]
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )


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

    def test_recursive_no_depth_uses_registrable_domain_equality(self) -> None:
        conds = build_where_clause(_exact("example.com"), True, None)
        # registrable_domain = ? is far faster than LIKE at 32 M rows
        assert len(conds) == 1
        assert "registrable_domain" in str(conds[0])
        assert "LIKE" not in str(conds[0])

    def test_recursive_no_depth_includes_root_domain(self) -> None:
        conds = build_where_clause(_exact("example.com"), True, None)
        # registrable_domain = 'example.com' matches the apex hostname itself
        # as well as all subdomains — no label-prefix requirement.
        assert "registrable_domain" in str(conds[0])
        assert "LIKE" not in str(conds[0])

    def test_recursive_no_depth_non_registrable_domain_uses_registrable_column(
        self,
    ) -> None:
        # When the caller supplies a non-eTLD+1 label (e.g. 'sub.cisco.com'),
        # the filter still targets registrable_domain.  The equality will return
        # no rows at runtime (sub.cisco.com is not itself a registrable domain),
        # which is the correct behaviour: use wildcard syntax or depth limiting
        # to search sub-subtrees.
        conds = build_where_clause(_exact("cae.cisco.com"), True, None)
        assert len(conds) == 1
        assert "registrable_domain" in str(conds[0])
        assert "LIKE" not in str(conds[0])

    def test_recursive_with_depth_adds_like_conditions(self) -> None:
        conds = build_where_clause(_exact("example.com"), True, 1)
        # depth conditions only: LIKE + NOT LIKE (no registrable_domain condition)
        assert len(conds) == 2

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

    def test_depth_means_at_most_not_exactly(self) -> None:
        # depth=2 must match 1-label-deep hosts too, not only 2-label-deep ones.
        # The LIKE anchor must be '%.domain', not '%.%.domain'.
        conds = build_where_clause(_exact("example.com"), True, 2)
        like_sql = next(
            _literal(c)
            for c in conds
            if "NOT" not in _literal(c) and "LIKE" in _literal(c)
        )
        # Single % wildcard before domain → PG literal renders it as '%%'
        assert like_sql.count("%%") == 1

    def test_depth_ceiling_grows_with_value(self) -> None:
        # The NOT LIKE pattern must have (depth+1) wildcards to cap at depth labels.
        # PG literal rendering doubles each %, so count '%%' groups.
        for d in (1, 2, 5):
            conds = build_where_clause(_exact("example.com"), True, d)
            not_like_sql = next(_literal(c) for c in conds if "NOT LIKE" in _literal(c))
            assert not_like_sql.count("%%") == d + 1


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
        # Both produce a registrable_domain equality (no LIKE) for fast lookup
        assert any("registrable_domain" in str(c) for c in wildcard_conds)
        assert not any("LIKE" in str(c) for c in wildcard_conds)

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
