"""Tests for ctpool.ct_api_schemas — raw CT HTTP API response models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from ctpool.ct_api_schemas import (
    CtEntriesResponse,
    CtLeafEntry,
    CtLogListResponse,
    CtLogOperator,
    SignedTreeHead,
)


def test_signed_tree_head_parses_valid_json() -> None:
    """Valid STH JSON fields produce a populated SignedTreeHead."""
    sth = SignedTreeHead(
        tree_size=1000,
        timestamp=1700000000000,
        sha256_root_hash="abc123",
        tree_head_signature="sig456",
    )
    assert sth.tree_size == 1000
    assert sth.sha256_root_hash == "abc123"


def test_signed_tree_head_missing_tree_size_raises() -> None:
    """Missing tree_size raises ValidationError."""
    with pytest.raises(ValidationError):
        SignedTreeHead(  # type: ignore[call-arg]
            timestamp=1700000000000,
            sha256_root_hash="abc123",
            tree_head_signature="sig456",
        )


def test_signed_tree_head_negative_tree_size_raises() -> None:
    """Negative tree_size raises ValidationError (ge=0 constraint)."""
    with pytest.raises(ValidationError):
        SignedTreeHead(
            tree_size=-1,
            timestamp=1700000000000,
            sha256_root_hash="abc123",
            tree_head_signature="sig456",
        )


def test_ct_entries_response_parses_entry_list() -> None:
    """Valid entries response with two entries parses correctly."""
    resp = CtEntriesResponse(
        entries=[
            CtLeafEntry(leaf_input="aGVsbG8=", extra_data="d29ybGQ="),
            CtLeafEntry(leaf_input="Zm9v", extra_data="YmFy"),
        ]
    )
    assert len(resp.entries) == 2


def test_ct_leaf_entry_requires_leaf_input() -> None:
    """Missing leaf_input raises ValidationError."""
    with pytest.raises(ValidationError):
        CtLeafEntry(extra_data="d29ybGQ=")  # type: ignore[call-arg]


def test_ct_entries_response_empty_list_allowed() -> None:
    """An empty entries list is a valid response."""
    resp = CtEntriesResponse(entries=[])
    assert resp.entries == []


def test_log_list_response_parses_chrome_format() -> None:
    """Chrome-format log list JSON with one operator and one log parses correctly."""
    data = {
        "version": "1.0.0",
        "log_list_timestamp": "2024-01-01T00:00:00Z",
        "operators": [
            {
                "name": "Google",
                "email": ["google-ct-logs@googlegroups.com"],
                "logs": [
                    {
                        "description": "Google 'Argon2024' log",
                        "log_id": "abc123==",
                        "key": "keydata==",
                        "url": "https://ct.googleapis.com/logs/argon2024/",
                        "mmd": 86400,
                        "state": {"usable": {"timestamp": "2024-01-01T00:00:00Z"}},
                    }
                ],
            }
        ],
    }
    result = CtLogListResponse.model_validate(data)
    assert len(result.operators) == 1
    assert result.operators[0].name == "Google"
    assert len(result.operators[0].logs) == 1


def test_log_list_response_empty_operators_allowed() -> None:
    """A log list with an empty operators list is valid."""
    result = CtLogListResponse(operators=[])
    assert result.operators == []


def test_ct_log_operator_has_default_empty_logs() -> None:
    """CtLogOperator.logs defaults to an empty list when not provided."""
    op = CtLogOperator(name="TestOp")
    assert op.logs == []
