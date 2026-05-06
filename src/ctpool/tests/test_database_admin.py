"""Tests for ctpool.database_admin helper functions."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.exc import SQLAlchemyError

from ctpool.config import Settings
from ctpool.database_admin import (
    create_database_if_missing_sync,
    database_exists_sync,
    recreate_database_sync,
    resolve_admin_database_url,
)
from ctpool.exceptions import DatabaseInitError, DatabasePrivilegeError


def _settings(**overrides: object) -> Settings:
    base = {"database_url": "postgresql+psycopg://ctpool:ctpool@localhost:5432/ctpool"}
    base.update(overrides)
    return Settings.model_validate(base)


def test_resolve_admin_database_url_prefers_explicit_admin_url() -> None:
    settings = _settings(
        database_admin_url="postgresql+psycopg://admin:secret@localhost:5432/postgres"
    )
    assert resolve_admin_database_url(settings).endswith("@localhost:5432/postgres")


def test_resolve_admin_database_url_derives_postgres_db() -> None:
    settings = _settings()
    assert resolve_admin_database_url(settings).endswith("@localhost:5432/postgres")


def test_resolve_admin_database_url_rejects_target_database() -> None:
    settings = _settings(
        database_admin_url="postgresql+psycopg://admin:secret@localhost:5432/ctpool"
    )
    with pytest.raises(DatabaseInitError, match="maintenance database"):
        resolve_admin_database_url(settings)


def test_resolve_admin_database_url_rejects_different_server() -> None:
    settings = _settings(
        database_admin_url="postgresql+psycopg://admin:secret@db.example:5432/postgres"
    )
    with pytest.raises(DatabaseInitError, match="same PostgreSQL server"):
        resolve_admin_database_url(settings)


def test_target_database_name_rejects_reserved_database() -> None:
    settings = _settings(
        database_url="postgresql+psycopg://ctpool:ctpool@localhost:5432/postgres"
    )
    with pytest.raises(DatabaseInitError, match="reserved PostgreSQL database"):
        database_exists_sync(settings)


def test_database_exists_sync_returns_true_when_database_present() -> None:
    connection = MagicMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = 1
    connection.execute.return_value = result
    engine = MagicMock()
    engine.connect.return_value.__enter__.return_value = connection
    engine.connect.return_value.__exit__.return_value = False

    with patch("ctpool.database_admin.create_engine", return_value=engine):
        assert database_exists_sync(_settings()) is True


def test_create_database_if_missing_issues_create_statement() -> None:
    connection = MagicMock()
    engine = MagicMock()
    engine.connect.return_value.__enter__.return_value = connection
    engine.connect.return_value.__exit__.return_value = False

    with (
        patch("ctpool.database_admin.database_exists_sync", return_value=False),
        patch("ctpool.database_admin.create_engine", return_value=engine),
    ):
        created = create_database_if_missing_sync(_settings())

    assert created is True
    connection.exec_driver_sql.assert_called_once_with(
        'CREATE DATABASE "ctpool" OWNER "ctpool"'
    )


def test_recreate_database_sync_drops_then_creates_when_present() -> None:
    connection = MagicMock()
    engine = MagicMock()
    engine.connect.return_value.__enter__.return_value = connection
    engine.connect.return_value.__exit__.return_value = False

    with (
        patch("ctpool.database_admin.database_exists_sync", return_value=True),
        patch("ctpool.database_admin.create_engine", return_value=engine),
    ):
        existed = recreate_database_sync(_settings())

    assert existed is True
    assert connection.execute.call_count == 1
    connection.exec_driver_sql.assert_any_call('DROP DATABASE IF EXISTS "ctpool"')
    connection.exec_driver_sql.assert_any_call(
        'CREATE DATABASE "ctpool" OWNER "ctpool"'
    )


def test_create_database_if_missing_raises_privilege_error() -> None:
    engine = MagicMock()
    engine.connect.return_value.__enter__.side_effect = SQLAlchemyError("boom")

    with (
        patch("ctpool.database_admin.database_exists_sync", return_value=False),
        patch("ctpool.database_admin.create_engine", return_value=engine),
    ):
        with pytest.raises(
            DatabasePrivilegeError, match="Unable to create.*PostgreSQL reported: boom"
        ):
            create_database_if_missing_sync(_settings())


def test_recreate_database_sync_includes_original_database_error() -> None:
    engine = MagicMock()
    connection = MagicMock()
    connection.exec_driver_sql.side_effect = SQLAlchemyError("permission denied")
    engine.connect.return_value.__enter__.return_value = connection
    engine.connect.return_value.__exit__.return_value = False

    with (
        patch("ctpool.database_admin.database_exists_sync", return_value=False),
        patch("ctpool.database_admin.create_engine", return_value=engine),
    ):
        with pytest.raises(
            DatabasePrivilegeError,
            match=(
                "Unable to drop and recreate.*PostgreSQL reported: permission denied"
            ),
        ):
            recreate_database_sync(_settings())
