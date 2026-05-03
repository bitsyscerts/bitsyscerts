"""Tests for ctpool.exceptions — domain exception hierarchy."""

from __future__ import annotations

import pytest

from ctpool.exceptions import (
    ConfigurationError,
    CtPoolError,
    DatabaseError,
    DiskGuardError,
    DispatcherError,
    FetchError,
    ParseError,
    RateLimitError,
)


def test_ct_pool_error_is_base_exception() -> None:
    """CtPoolError inherits from the built-in Exception."""
    assert issubclass(CtPoolError, Exception)


def test_fetch_error_is_subclass_of_ct_pool_error() -> None:
    """FetchError is a CtPoolError so callers can catch the whole domain."""
    assert issubclass(FetchError, CtPoolError)


def test_parse_error_carries_message() -> None:
    """ParseError preserves the message passed at construction time."""
    err = ParseError("bad leaf input")
    assert str(err) == "bad leaf input"


def test_database_error_chains_original_exception() -> None:
    """DatabaseError can wrap an original exception via __cause__."""
    original = RuntimeError("db down")
    err = DatabaseError("write failed")
    err.__cause__ = original
    assert err.__cause__ is original


def test_disk_guard_error_is_ct_pool_error() -> None:
    """DiskGuardError is a CtPoolError."""
    assert issubclass(DiskGuardError, CtPoolError)


def test_rate_limit_error_is_ct_pool_error() -> None:
    """RateLimitError is a CtPoolError."""
    assert issubclass(RateLimitError, CtPoolError)


def test_configuration_error_is_ct_pool_error() -> None:
    """ConfigurationError is a CtPoolError."""
    assert issubclass(ConfigurationError, CtPoolError)


def test_dispatcher_error_is_ct_pool_error() -> None:
    """DispatcherError is a CtPoolError."""
    assert issubclass(DispatcherError, CtPoolError)


@pytest.mark.parametrize(
    "exc_class",
    [
        FetchError,
        ParseError,
        DatabaseError,
        DiskGuardError,
        RateLimitError,
        ConfigurationError,
        DispatcherError,
    ],
)
def test_all_domain_exceptions_catchable_as_ct_pool_error(
    exc_class: type[CtPoolError],
) -> None:
    """Every domain exception can be caught as CtPoolError."""
    with pytest.raises(CtPoolError):
        raise exc_class("test")
