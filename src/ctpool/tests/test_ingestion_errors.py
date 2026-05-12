"""Tests for ctpool.ingestion_errors classifier."""

from __future__ import annotations

import pytest

from ctpool.exceptions import (
    ConfigurationError,
    DatabaseError,
    DispatcherError,
    FetchError,
    ParseError,
    RateLimitError,
    UnsupportedEntryTypeError,
)
from ctpool.ingestion_errors import (
    IngestionFailureClass,
    classify_ingestion_error,
)


@pytest.mark.parametrize(
    ("exc", "expected"),
    [
        (FetchError("net"), IngestionFailureClass.RETRYABLE_FETCH),
        (DatabaseError("deadlock"), IngestionFailureClass.RETRYABLE_DATABASE),
        (ParseError("bad asn1"), IngestionFailureClass.TERMINAL_PARSE),
        (
            UnsupportedEntryTypeError("v3"),
            IngestionFailureClass.TERMINAL_UNSUPPORTED,
        ),
        (
            ConfigurationError("missing-secret"),
            IngestionFailureClass.FATAL_CONFIGURATION,
        ),
        (
            DispatcherError("no-eligible-logs"),
            IngestionFailureClass.FATAL_LOG,
        ),
        (RuntimeError("boom"), IngestionFailureClass.UNKNOWN),
    ],
)
def test_classifier_table_driven(
    exc: Exception, expected: IngestionFailureClass
) -> None:
    """Each documented exception maps to the expected operational class."""
    failure = classify_ingestion_error(exc)
    assert failure.failure_class is expected
    assert failure.error_type == exc.__class__.__name__


def test_classifier_rate_limit_carries_retry_after() -> None:
    """RateLimitError preserves Retry-After hint for cooldown timing."""
    failure = classify_ingestion_error(RateLimitError("429", retry_after_seconds=42))
    assert failure.failure_class is IngestionFailureClass.RETRYABLE_RATE_LIMIT
    assert failure.retry_after_seconds == 42
    assert failure.is_retryable is True


def test_classifier_terminal_entry_flag() -> None:
    """ParseError-class failures report is_terminal_entry True."""
    failure = classify_ingestion_error(ParseError("bad"))
    assert failure.is_terminal_entry is True
    assert failure.is_fatal is False


def test_classifier_fatal_flag() -> None:
    """Configuration failures report is_fatal True."""
    failure = classify_ingestion_error(ConfigurationError("missing"))
    assert failure.is_fatal is True
    assert failure.is_retryable is False


def test_classifier_unsupported_takes_precedence_over_parse() -> None:
    """UnsupportedEntryTypeError subclasses ParseError; check precedence."""
    failure = classify_ingestion_error(UnsupportedEntryTypeError("v3"))
    assert failure.failure_class is IngestionFailureClass.TERMINAL_UNSUPPORTED


def test_classifier_truncates_long_message() -> None:
    """Long error messages are truncated for durable storage."""
    failure = classify_ingestion_error(RuntimeError("x" * 5000))
    assert len(failure.error_message) <= 500
