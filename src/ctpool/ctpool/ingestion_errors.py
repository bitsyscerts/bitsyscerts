"""Centralized ingestion failure classification for the per-log path.

A single mapping from raised exceptions to operationally meaningful classes
keeps retry, cooldown, and durable-outcome logic consistent everywhere
ingestion failures are handled.

Classification has three top-level intents:

- ``RETRYABLE`` — the current batch should be re-fetched later. The
  per-log durable checkpoint is not advanced.
- ``TERMINAL_ENTRY`` — a single CT entry is bad. A row is written to
  ``ct_entry_outcomes`` and the worker continues to the next entry; the
  checkpoint advances past the bad index.
- ``FATAL`` — a non-recoverable condition. The log is paused or marked
  ``error`` so an operator can intervene.

These categories intentionally mirror the per-log status vocabulary used
in :mod:`ctpool.worker_claim`.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from ctpool.exceptions import (
    ConfigurationError,
    DatabaseError,
    DispatcherError,
    FetchError,
    ParseError,
    RateLimitError,
    UnsupportedEntryTypeError,
)


class IngestionFailureClass(StrEnum):
    """Operational classification of an ingestion failure."""

    RETRYABLE_RATE_LIMIT = "retryable_rate_limit"
    RETRYABLE_FETCH = "retryable_fetch_error"
    RETRYABLE_DATABASE = "retryable_database_error"
    TERMINAL_PARSE = "terminal_parse_error"
    TERMINAL_UNSUPPORTED = "terminal_unsupported_entry"
    TERMINAL_POLICY = "terminal_policy_skip"
    FATAL_LOG = "fatal_log_error"
    FATAL_CONFIGURATION = "fatal_configuration_error"
    UNKNOWN = "unknown_error"


_RETRYABLE_CLASSES = frozenset(
    {
        IngestionFailureClass.RETRYABLE_RATE_LIMIT,
        IngestionFailureClass.RETRYABLE_FETCH,
        IngestionFailureClass.RETRYABLE_DATABASE,
        IngestionFailureClass.UNKNOWN,
    }
)
_TERMINAL_ENTRY_CLASSES = frozenset(
    {
        IngestionFailureClass.TERMINAL_PARSE,
        IngestionFailureClass.TERMINAL_UNSUPPORTED,
        IngestionFailureClass.TERMINAL_POLICY,
    }
)
_FATAL_CLASSES = frozenset(
    {
        IngestionFailureClass.FATAL_LOG,
        IngestionFailureClass.FATAL_CONFIGURATION,
    }
)


@dataclass(frozen=True)
class IngestionFailure:
    """A classified failure with retry hint."""

    failure_class: IngestionFailureClass
    error_type: str
    error_message: str
    retry_after_seconds: int | None = None

    @property
    def is_retryable(self) -> bool:
        """Whether the batch should be retried in place."""
        return self.failure_class in _RETRYABLE_CLASSES

    @property
    def is_terminal_entry(self) -> bool:
        """Whether the failure is a per-entry terminal condition."""
        return self.failure_class in _TERMINAL_ENTRY_CLASSES

    @property
    def is_fatal(self) -> bool:
        """Whether the failure should pause or error the log."""
        return self.failure_class in _FATAL_CLASSES


def classify_ingestion_error(exc: BaseException) -> IngestionFailure:
    """Return the operational classification for *exc*.

    The classifier is intentionally exhaustive over the project's domain
    exception hierarchy and falls back to ``UNKNOWN`` (treated as
    retryable) for anything else.
    """
    error_type = exc.__class__.__name__
    message = _short_message(str(exc))

    if isinstance(exc, RateLimitError):
        return IngestionFailure(
            failure_class=IngestionFailureClass.RETRYABLE_RATE_LIMIT,
            error_type=error_type,
            error_message=message,
            retry_after_seconds=exc.retry_after_seconds,
        )
    # UnsupportedEntryTypeError is a subclass of ParseError; check it first.
    if isinstance(exc, UnsupportedEntryTypeError):
        return IngestionFailure(
            failure_class=IngestionFailureClass.TERMINAL_UNSUPPORTED,
            error_type=error_type,
            error_message=message,
        )
    if isinstance(exc, ParseError):
        return IngestionFailure(
            failure_class=IngestionFailureClass.TERMINAL_PARSE,
            error_type=error_type,
            error_message=message,
        )
    if isinstance(exc, FetchError):
        return IngestionFailure(
            failure_class=IngestionFailureClass.RETRYABLE_FETCH,
            error_type=error_type,
            error_message=message,
        )
    if isinstance(exc, DatabaseError):
        return IngestionFailure(
            failure_class=IngestionFailureClass.RETRYABLE_DATABASE,
            error_type=error_type,
            error_message=message,
        )
    if isinstance(exc, ConfigurationError):
        return IngestionFailure(
            failure_class=IngestionFailureClass.FATAL_CONFIGURATION,
            error_type=error_type,
            error_message=message,
        )
    if isinstance(exc, DispatcherError):
        return IngestionFailure(
            failure_class=IngestionFailureClass.FATAL_LOG,
            error_type=error_type,
            error_message=message,
        )
    return IngestionFailure(
        failure_class=IngestionFailureClass.UNKNOWN,
        error_type=error_type,
        error_message=message,
    )


def _short_message(text: str, *, limit: int = 500) -> str:
    """Truncate long messages for durable storage."""
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."
