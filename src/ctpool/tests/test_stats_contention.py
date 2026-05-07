"""Unit tests for ctpool.stats_contention pure functions."""

from __future__ import annotations

from datetime import UTC, datetime

from ctpool.db_contention_types import DbContentionOperatorSnapshot
from ctpool.stats_contention import render_db_contention_panel


def _snapshot(**kwargs) -> DbContentionOperatorSnapshot:
    defaults: dict = {
        "status": "healthy",
        "degraded_mode_active": False,
        "pressure_ema": 0.12,
        "base_sleep_seconds": 0.05,
        "shared_batch_size_cap": None,
        "effective_batch_size_cap": None,
        "updated_at": None,
        "notes": [],
    }
    defaults.update(kwargs)
    return DbContentionOperatorSnapshot(**defaults)


def test_render_panel_contains_status():
    panel = render_db_contention_panel(_snapshot(status="healthy"))
    assert "healthy" in panel.renderable


def test_render_panel_contains_pressure():
    panel = render_db_contention_panel(_snapshot(pressure_ema=0.456))
    assert "0.456" in panel.renderable


def test_render_panel_contains_base_sleep():
    panel = render_db_contention_panel(_snapshot(base_sleep_seconds=1.23))
    assert "1.23" in panel.renderable


def test_render_panel_no_cap_shows_dash():
    panel = render_db_contention_panel(_snapshot(effective_batch_size_cap=None))
    assert "—" in panel.renderable


def test_render_panel_with_cap_shows_value():
    panel = render_db_contention_panel(_snapshot(effective_batch_size_cap=500))
    assert "500" in panel.renderable


def test_render_panel_no_updated_at_skips_line():
    panel = render_db_contention_panel(_snapshot(updated_at=None))
    assert "Updated:" not in panel.renderable


def test_render_panel_with_updated_at_shows_timestamp():
    ts = datetime(2024, 6, 1, 12, 0, 0, tzinfo=UTC)
    panel = render_db_contention_panel(_snapshot(updated_at=ts))
    assert "Updated:" in panel.renderable


def test_render_panel_with_notes_shows_them():
    panel = render_db_contention_panel(_snapshot(notes=["note one", "note two"]))
    assert "note one" in panel.renderable
    assert "note two" in panel.renderable


def test_render_panel_throttling_status():
    panel = render_db_contention_panel(_snapshot(status="throttling"))
    assert "throttling" in panel.renderable


def test_render_panel_unknown_status_uses_white():
    panel = render_db_contention_panel(_snapshot(status="unknown_status"))
    assert "unknown_status" in panel.renderable
