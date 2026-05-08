"""Unit tests for outcome_constants module."""

from __future__ import annotations

import pytest

from ctpool.outcome_constants import (
    ALL_OUTCOMES,
    OUTCOME_PARSE_ERROR,
    OUTCOME_SKIPPED_BY_POLICY,
    OUTCOME_STORED,
    OUTCOME_UNSUPPORTED_ENTRY_TYPE,
    OUTCOME_WRITE_ERROR,
)


def test_all_outcomes_contains_all_constants() -> None:
    """ALL_OUTCOMES must include every defined OUTCOME_* constant."""
    assert OUTCOME_STORED in ALL_OUTCOMES
    assert OUTCOME_PARSE_ERROR in ALL_OUTCOMES
    assert OUTCOME_UNSUPPORTED_ENTRY_TYPE in ALL_OUTCOMES
    assert OUTCOME_SKIPPED_BY_POLICY in ALL_OUTCOMES
    assert OUTCOME_WRITE_ERROR in ALL_OUTCOMES


def test_all_outcomes_has_exactly_five_entries() -> None:
    """ALL_OUTCOMES must have exactly five entries — no accidental extras."""
    assert len(ALL_OUTCOMES) == 5


@pytest.mark.parametrize(
    "constant,expected",
    [
        (OUTCOME_STORED, "stored"),
        (OUTCOME_PARSE_ERROR, "parse_error"),
        (OUTCOME_UNSUPPORTED_ENTRY_TYPE, "unsupported_entry_type"),
        (OUTCOME_SKIPPED_BY_POLICY, "skipped_by_policy"),
        (OUTCOME_WRITE_ERROR, "write_error"),
    ],
)
def test_constant_values(constant: str, expected: str) -> None:
    """Each constant has the expected string value."""
    assert constant == expected
