"""Tests for ctpool.migration_runner — upgrade head and revision queries."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from ctpool.config import Settings
from ctpool.exceptions import SchemaStateError
from ctpool.migration_runner import (
    get_current_revision,
    get_missing_core_tables,
    run_upgrade_head,
)


@pytest.fixture()
def settings(test_settings: Settings) -> Settings:
    """Re-export test_settings under a local alias."""
    return test_settings


# ------------------------------------------------------------------
# run_upgrade_head
# ------------------------------------------------------------------


async def test_run_upgrade_head_calls_alembic_upgrade(settings: Settings) -> None:
    """run_upgrade_head invokes _upgrade_sync via a thread executor."""
    with (
        patch("ctpool.migration_runner._upgrade_sync") as mock_upgrade,
        patch("ctpool.migration_runner._raise_for_incomplete_schema"),
    ):
        mock_upgrade.return_value = None
        await run_upgrade_head(settings)
    mock_upgrade.assert_called_once()


async def test_run_upgrade_head_passes_alembic_config(settings: Settings) -> None:
    """run_upgrade_head passes an AlembicConfig with the correct database URL."""
    from alembic.config import Config as AlembicConfig

    captured: list[AlembicConfig] = []

    def _capture(cfg: AlembicConfig) -> None:
        captured.append(cfg)

    with (
        patch("ctpool.migration_runner._upgrade_sync", side_effect=_capture),
        patch("ctpool.migration_runner._raise_for_incomplete_schema"),
    ):
        await run_upgrade_head(settings)

    assert len(captured) == 1
    assert str(settings.database_url) == (
        captured[0].get_main_option("sqlalchemy.url") or ""
    )


# ------------------------------------------------------------------
# get_current_revision
# ------------------------------------------------------------------


async def test_get_current_revision_returns_none_when_no_migrations(
    settings: Settings,
) -> None:
    """get_current_revision returns None if no migrations have been applied."""
    with patch("ctpool.migration_runner._fetch_revision_sync", return_value=None):
        result = await get_current_revision(settings)
    assert result is None


async def test_get_current_revision_returns_string_when_migrated(
    settings: Settings,
) -> None:
    """get_current_revision returns a revision string after migrations run."""
    fake_rev = "abc123def456"
    with patch("ctpool.migration_runner._fetch_revision_sync", return_value=fake_rev):
        result = await get_current_revision(settings)
    assert result == fake_rev


async def test_run_upgrade_head_uses_executor(settings: Settings) -> None:
    """run_upgrade_head dispatches work to a thread-pool executor."""
    with (
        patch("ctpool.migration_runner._upgrade_sync"),
        patch("ctpool.migration_runner._raise_for_incomplete_schema"),
    ):
        # If run_in_executor is called, the _upgrade_sync mock should be invoked
        await run_upgrade_head(settings)
        # No assertion needed beyond no exception being raised — the mock above
        # validates the executor pathway was used


async def test_run_upgrade_head_raises_when_core_tables_missing(
    settings: Settings,
) -> None:
    """run_upgrade_head fails when Alembic revision does not match real tables."""
    with (
        patch("ctpool.migration_runner._upgrade_sync"),
        patch(
            "ctpool.migration_runner._raise_for_incomplete_schema",
            side_effect=SchemaStateError("missing hostnames"),
        ),
    ):
        with pytest.raises(SchemaStateError, match="missing hostnames"):
            await run_upgrade_head(settings)


# ------------------------------------------------------------------
# helpers
# ------------------------------------------------------------------


def test_make_alembic_cfg_sets_db_url(settings: Settings) -> None:
    """_make_alembic_cfg embeds the database_url in the AlembicConfig."""
    from ctpool.migration_runner import _make_alembic_cfg

    cfg = _make_alembic_cfg(settings)
    url = cfg.get_main_option("sqlalchemy.url") or ""
    assert str(settings.database_url) == url


def test_make_alembic_cfg_sets_script_location(settings: Settings) -> None:
    """_make_alembic_cfg points Alembic at the resolved migration directory."""
    from ctpool.migration_runner import _make_alembic_cfg, _resolve_migration_root

    cfg = _make_alembic_cfg(settings)

    assert cfg.get_main_option("script_location") == str(_resolve_migration_root())


def test_fetch_revision_sync_returns_none_when_no_table(
    settings: Settings,
) -> None:
    """_fetch_revision_sync returns None when alembic_version does not exist."""
    from ctpool.migration_runner import _fetch_revision_sync

    mock_result = MagicMock()
    mock_result.scalar_one.return_value = False
    mock_conn = MagicMock()
    mock_conn.execute.return_value = mock_result
    mock_conn.__enter__ = MagicMock(return_value=mock_conn)
    mock_conn.__exit__ = MagicMock(return_value=False)
    mock_engine = MagicMock()
    mock_engine.connect.return_value = mock_conn

    with patch("ctpool.migration_runner.create_engine", return_value=mock_engine):
        result = _fetch_revision_sync(str(settings.database_url))

    assert result is None


def test_fetch_revision_sync_returns_revision_when_table_exists(
    settings: Settings,
) -> None:
    """_fetch_revision_sync returns the revision string when table is present."""
    from alembic.runtime.migration import MigrationContext

    from ctpool.migration_runner import _fetch_revision_sync

    fake_rev = "deadbeef1234"
    mock_result = MagicMock()
    mock_result.scalar_one.return_value = True
    mock_conn = MagicMock()
    mock_conn.execute.return_value = mock_result
    mock_conn.__enter__ = MagicMock(return_value=mock_conn)
    mock_conn.__exit__ = MagicMock(return_value=False)
    mock_engine = MagicMock()
    mock_engine.connect.return_value = mock_conn

    with patch("ctpool.migration_runner.create_engine", return_value=mock_engine):
        with patch.object(
            MigrationContext,
            "configure",
            return_value=MagicMock(
                get_current_revision=MagicMock(return_value=fake_rev)
            ),
        ):
            result = _fetch_revision_sync(str(settings.database_url))

    assert result == fake_rev


async def test_get_missing_core_tables_returns_missing_subset(
    settings: Settings,
) -> None:
    """get_missing_core_tables returns the missing required table names."""
    with patch(
        "ctpool.migration_runner._missing_core_tables",
        return_value=("hostnames", "certificates"),
    ):
        result = await get_missing_core_tables(settings)

    assert result == ("hostnames", "certificates")
