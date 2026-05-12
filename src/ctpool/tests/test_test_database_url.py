"""Tests for safe integration-test database URL resolution."""

from __future__ import annotations

import pytest

from ctpool.test_database_url import resolve_test_database_url


def test_resolve_test_database_url_derives_sibling_test_database() -> None:
    """Live DATABASE_URL values are rewritten to a sibling *_test database."""
    resolved = resolve_test_database_url(
        source_database_url="postgresql+psycopg://u:p@localhost:5432/ctpool",
        explicit_test_database_url=None,
        fallback_database_url="postgresql+psycopg://u:p@localhost:5432/ctpool_test",
    )

    assert resolved.endswith("/ctpool_test")


def test_resolve_test_database_url_keeps_existing_test_database_name() -> None:
    """DATABASE_URL values that already point at *_test stay unchanged."""
    resolved = resolve_test_database_url(
        source_database_url="postgresql+psycopg://u:p@localhost:5432/ctpool_test",
        explicit_test_database_url=None,
        fallback_database_url="postgresql+psycopg://u:p@localhost:5432/ctpool_test",
    )

    assert resolved.endswith("/ctpool_test")


def test_resolve_test_database_url_prefers_explicit_override() -> None:
    """BITSYSCERTS_TEST_DATABASE_URL overrides the derived sibling database."""
    resolved = resolve_test_database_url(
        source_database_url="postgresql+psycopg://u:p@localhost:5432/ctpool",
        explicit_test_database_url=(
            "postgresql+psycopg://u:p@localhost:5432/isolated_integration"
        ),
        fallback_database_url="postgresql+psycopg://u:p@localhost:5432/ctpool_test",
    )

    assert resolved.endswith("/isolated_integration")


def test_resolve_test_database_url_rejects_live_database_target() -> None:
    """An explicit override cannot point at the same live database as DATABASE_URL."""
    with pytest.raises(RuntimeError, match="Refusing to run integration tests"):
        resolve_test_database_url(
            source_database_url="postgresql+psycopg://u:p@localhost:5432/ctpool",
            explicit_test_database_url="postgresql+psycopg://u:p@localhost:5432/ctpool",
            fallback_database_url="postgresql+psycopg://u:p@localhost:5432/ctpool_test",
        )
