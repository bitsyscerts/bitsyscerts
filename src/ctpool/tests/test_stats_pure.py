"""Unit tests for ctpool.stats pure functions (no DB required)."""

from __future__ import annotations

from ctpool.stats import _format_eta  # noqa: PLC2701

# ---------------------------------------------------------------------------
# _format_eta
# ---------------------------------------------------------------------------


def test_format_eta_returns_dash_when_rate_is_none():
    assert _format_eta(1000, None) == "—"


def test_format_eta_returns_dash_when_rate_is_zero():
    assert _format_eta(1000, 0.0) == "—"


def test_format_eta_returns_dash_when_lag_is_zero():
    assert _format_eta(0, 10.0) == "—"


def test_format_eta_returns_dash_when_lag_is_negative():
    assert _format_eta(-5, 10.0) == "—"


def test_format_eta_one_hour_exact():
    result = _format_eta(3600, 1.0)
    assert result == "01:00:00"


def test_format_eta_under_one_minute():
    result = _format_eta(45, 1.0)
    assert result == "00:00:45"


def test_format_eta_one_day_plus():
    # 90000 seconds = 1 day 1 hour
    result = _format_eta(90000, 1.0)
    assert result == "1.01:00:00"


def test_format_eta_many_days():
    result = _format_eta(3 * 86400, 1.0)
    assert result == "3.00:00:00"


def test_format_eta_fast_rate_rounds_down():
    result = _format_eta(100, 50.0)
    # 100/50 = 2 seconds
    assert result == "00:00:02"
