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
    """Exact hostname match, or registrable-domain search when recursive=True."""
    if not recursive:
        return [Hostname.hostname == value]
    conditions: list[ColumnElement[bool]] = [
        Hostname.registrable_domain == value,
    ]
    if depth is not None:
        # depth LIKE patterns already exclude the root via the leading label
        conditions.extend(_depth_conditions(value, depth))
    else:
        # Exclude the root domain itself — recursive means subdomains only
        conditions.append(Hostname.hostname != value)
    return conditions


def _depth_conditions(domain: str, depth: int) -> list[ColumnElement[bool]]:
    """Restrict to exactly *depth* DNS labels above *domain*.

    depth=1: LIKE '%.domain' AND NOT LIKE '%.%.domain'
    depth=2: LIKE '%.%.domain' AND NOT LIKE '%.%.%.domain'
    """
    prefix_exact = ".".join(["%"] * depth)
    prefix_deeper = ".".join(["%"] * (depth + 1))
    return [
        Hostname.hostname.like(f"{prefix_exact}.{domain}"),
        ~Hostname.hostname.like(f"{prefix_deeper}.{domain}"),
    ]
