"""Converts a ParsedQuery + recursive/depth flags to SQLAlchemy WHERE clauses."""

from __future__ import annotations

from ctpool.models.hostname import Hostname
from sqlalchemy import ColumnElement

from certsapi.hostnames.query_parser import ParsedQuery, QueryStrategy


def build_where_clause(
    parsed: ParsedQuery,
    recursive: bool,
    depth: int | None,
) -> list[ColumnElement[bool]]:
    """Return SQLAlchemy WHERE conditions for the given query and options."""
    if parsed.strategy == QueryStrategy.regex:
        return [Hostname.hostname.op("~")(parsed.value)]
    if parsed.strategy == QueryStrategy.wildcard:
        if recursive:
            # *.example.com + recursive=True → same as example.com + recursive
            # (the *.  is implicit; recursive already implies "all subdomains")
            return _exact_or_domain_conditions(parsed.value, True, depth)
        return _wildcard_conditions(parsed.value)
    return _exact_or_domain_conditions(parsed.value, recursive, depth)


def _wildcard_conditions(domain: str) -> list[ColumnElement[bool]]:
    """Match hostnames with exactly one DNS label before *domain*."""
    return [
        Hostname.hostname.like(f"%.{domain}"),
        ~Hostname.hostname.like(f"%.%.{domain}"),
    ]


def _exact_or_domain_conditions(
    value: str,
    recursive: bool,
    depth: int | None,
) -> list[ColumnElement[bool]]:
    """Exact hostname match, or registrable-domain search when recursive=True.

    When recursive=True and no depth is given, matches all hostnames whose
    ``registrable_domain`` equals *value*.  This uses the B-tree composite
    index ``idx_hostnames_reg_domain_not_before`` / ``_not_after`` and is
    orders of magnitude faster than a leading-wildcard LIKE scan at scale.

    Callers should supply an eTLD+1 registrable domain (e.g. ``cisco.com``)
    as the query value when ``recursive=True``.  If a deeper label is supplied
    (e.g. ``sub.cisco.com``) the equality filter will return no rows because
    that label is not itself a registrable domain.  Use the ``*.sub.cisco.com``
    wildcard syntax or a depth-limited recursive query for sub-subtree searches.

    When depth is specified the search is still LIKE-based because depth
    limiting requires label-counting via NOT LIKE patterns.
    """
    if not recursive:
        return [Hostname.hostname == value]
    if depth is not None:
        return _depth_conditions(value, depth)
    return [Hostname.registrable_domain == value]


def _depth_conditions(domain: str, depth: int) -> list[ColumnElement[bool]]:
    """Restrict to at most *depth* DNS labels above *domain*.

    depth=1: LIKE '%.domain' AND NOT LIKE '%.%.domain'
    depth=2: LIKE '%.domain' AND NOT LIKE '%.%.%.domain'
    depth=5: LIKE '%.domain' AND NOT LIKE '%.%.%.%.%.%.domain'
    """
    prefix_deeper = ".".join(["%"] * (depth + 1))
    return [
        Hostname.hostname.like(f"%.{domain}"),
        ~Hostname.hostname.like(f"{prefix_deeper}.{domain}"),
    ]
