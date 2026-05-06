"""Tests for ctpool.config — Settings validation and singleton behaviour."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from ctpool.config import Settings, get_settings


def test_loads_all_required_fields_from_env() -> None:
    """Settings loads successfully when DATABASE_URL is provided."""
    s = Settings.model_validate(
        {"database_url": "postgresql+psycopg://u:p@localhost:5432/db"}
    )
    assert str(s.database_url).startswith("postgresql")


def test_missing_database_url_raises_validation_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Omitting DATABASE_URL raises a pydantic ValidationError immediately."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(ValidationError):
        Settings.model_validate({})


def test_default_backfill_days_is_180() -> None:
    """CT_BACKFILL_DAYS defaults to 180."""
    s = Settings.model_validate(
        {"database_url": "postgresql+psycopg://u:p@localhost:5432/db"}
    )
    assert s.ct_backfill_days == 180


def test_default_tail_interval_is_300() -> None:
    """CT_TAIL_INTERVAL_SECONDS defaults to 300."""
    s = Settings.model_validate(
        {"database_url": "postgresql+psycopg://u:p@localhost:5432/db"}
    )
    assert s.ct_tail_interval_seconds == 300


def test_invalid_database_url_raises_validation_error() -> None:
    """A non-postgresql URL scheme is rejected by PostgresDsn validation."""
    with pytest.raises(ValidationError):
        Settings.model_validate({"database_url": "sqlite:///local.db"})


def test_get_settings_returns_singleton() -> None:
    """Two calls to get_settings() return the identical object."""
    # get_settings() requires DATABASE_URL in the environment; it will only
    # work if the env var is set, which it is in the dev container.  If not
    # set this test is skipped gracefully by catching the ValidationError.
    try:
        a = get_settings()
        b = get_settings()
        assert a is b
    except ValidationError:
        pytest.skip("DATABASE_URL not set in environment — singleton test skipped")


def test_ct_log_list_url_is_compile_time_constant() -> None:
    """ct_log_list_url is the trusted Chrome CT log list URL (SSRF prevention)."""
    s = Settings.model_validate(
        {"database_url": "postgresql+psycopg://u:p@localhost:5432/db"}
    )
    assert s.ct_log_list_url == "https://www.gstatic.com/ct/log_list/v3/log_list.json"
