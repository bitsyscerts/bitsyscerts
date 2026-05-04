"""Hostname query string parser: classifies q into EXACT, WILDCARD, or REGEX."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

from certsapi.hostnames.exceptions import InvalidQueryError

_RE_PREFIX = "re:"
_WILDCARD_PREFIX = "*."


class QueryStrategy(StrEnum):
    """Classification of a hostname search query string."""

    exact = "exact"
    wildcard = "wildcard"
    regex = "regex"


@dataclass(frozen=True, slots=True)
class ParsedQuery:
    """Result of parse_query: the detected strategy and extracted value."""

    strategy: QueryStrategy
    value: str


def parse_query(q: str) -> ParsedQuery:
    """Classify *q* and return a ParsedQuery.

    Raises:
        InvalidQueryError: For empty input, invalid regex pattern, or
            malformed wildcard expression.
    """
    if not q.strip():
        raise InvalidQueryError("Query string must not be empty")
    if q.startswith(_RE_PREFIX):
        return _parse_regex(q[len(_RE_PREFIX) :])
    if q.startswith(_WILDCARD_PREFIX):
        return _parse_wildcard(q[len(_WILDCARD_PREFIX) :])
    return ParsedQuery(strategy=QueryStrategy.exact, value=q)


def _parse_regex(pattern: str) -> ParsedQuery:
    """Validate and return a REGEX ParsedQuery."""
    if not pattern:
        raise InvalidQueryError("Regex pattern after 're:' must not be empty")
    try:
        re.compile(pattern)
    except re.error as exc:
        raise InvalidQueryError(f"Invalid regex pattern: {exc}") from exc
    return ParsedQuery(strategy=QueryStrategy.regex, value=pattern)


def _parse_wildcard(suffix: str) -> ParsedQuery:
    """Validate and return a WILDCARD ParsedQuery."""
    if not suffix:
        raise InvalidQueryError("Wildcard query must include a domain after '*.'")
    if "*" in suffix:
        raise InvalidQueryError(
            "Only one wildcard '*' is allowed and must appear as a '.*.' prefix"
        )
    return ParsedQuery(strategy=QueryStrategy.wildcard, value=suffix)
