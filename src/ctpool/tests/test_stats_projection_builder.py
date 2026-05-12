"""Unit tests for ctpool.stats_projection_builder."""

from __future__ import annotations

from unittest.mock import MagicMock

from ctpool.stats_projection_builder import (
    _build_projection_base,
    _resolve_effective_progress,
    build_projection_dict,
)

# ---------------------------------------------------------------------------
# _resolve_effective_progress
# ---------------------------------------------------------------------------


class TestResolveEffectiveProgress:
    """_resolve_effective_progress returns the right source of truth."""

    def test_uses_backfill_when_planned_total_nonzero(self) -> None:
        total, completed, basis = _resolve_effective_progress(
            {"planned_total": 10_000, "planned_completed": 500},
            ct_log_progress={"planned_total": 99_000, "planned_completed": 1_000},
        )
        assert total == 10_000
        assert completed == 500
        assert basis == "backfill_ranges"

    def test_falls_back_to_ct_log_when_backfill_zero(self) -> None:
        total, completed, basis = _resolve_effective_progress(
            {"planned_total": 0, "planned_completed": 0},
            ct_log_progress={"planned_total": 50_000, "planned_completed": 3_000},
        )
        assert total == 50_000
        assert completed == 3_000
        assert basis == "ct_log_tree_sizes"

    def test_returns_none_basis_when_both_zero(self) -> None:
        total, completed, basis = _resolve_effective_progress(
            {"planned_total": 0, "planned_completed": 0},
            ct_log_progress={"planned_total": 0, "planned_completed": 0},
        )
        assert total == 0
        assert completed == 0
        assert basis == "none"

    def test_returns_none_basis_when_ct_log_progress_is_none(self) -> None:
        total, completed, basis = _resolve_effective_progress(
            {"planned_total": 0, "planned_completed": 0},
            ct_log_progress=None,
        )
        assert total == 0
        assert completed == 0
        assert basis == "none"

    def test_backfill_takes_precedence_over_ct_log(self) -> None:
        total, _, basis = _resolve_effective_progress(
            {"planned_total": 1, "planned_completed": 1},
            ct_log_progress={"planned_total": 9_999, "planned_completed": 0},
        )
        assert basis == "backfill_ranges"
        assert total == 1

    def test_handles_missing_keys_gracefully(self) -> None:
        total, completed, basis = _resolve_effective_progress(
            {},  # no keys
            ct_log_progress=None,
        )
        assert total == 0
        assert completed == 0
        assert basis == "none"


# ---------------------------------------------------------------------------
# _build_projection_base
# ---------------------------------------------------------------------------


class TestBuildProjectionBase:
    """_build_projection_base produces the correct static base fields."""

    _COUNTS = {
        "observations": 100,
        "certificates": 40,
        "hostnames": 30,
        "cert_hostnames": 60,
    }

    def test_all_expected_keys_present(self) -> None:
        base = _build_projection_base(self._COUNTS, 1_000_000, 10_000, 500)
        for key in (
            "database_size_bytes",
            "ct_observations_count",
            "certificates_count",
            "hostnames_count",
            "certificate_hostnames_count",
            "planned_observations_total",
            "planned_observations_completed",
            "planned_observations_remaining",
        ):
            assert key in base, f"Missing key: {key}"

    def test_remaining_is_clamped_at_zero(self) -> None:
        base = _build_projection_base(self._COUNTS, 100, 1_000, 2_000)
        assert base["planned_observations_remaining"] == 0

    def test_completed_capped_at_total(self) -> None:
        base = _build_projection_base(self._COUNTS, 100, 1_000, 5_000)
        assert base["planned_observations_completed"] == 1_000


# ---------------------------------------------------------------------------
# build_projection_dict — fresh install (backfill empty, ct_log present)
# ---------------------------------------------------------------------------


def _make_global_counts(obs: int = 0) -> dict[str, int]:
    return {
        "observations": obs,
        "certificates": 0,
        "hostnames": 0,
        "cert_hostnames": 0,
    }


def _make_settings(profile: str = "lite") -> MagicMock:
    s = MagicMock()
    s.storage_profile = profile
    s.cert_storage_mode = "none"
    s.hostname_retention_mode = "all"
    s.backfill_days = 90
    s.cert_retention_days = 7
    s.observation_retention_days = 7
    s.entry_outcome_retention_days = 7
    return s


class TestBuildProjectionDictFreshInstall:
    """build_projection_dict works on a fresh install with no observations."""

    def test_returns_available_when_ct_log_progress_nonzero(self) -> None:
        result = build_projection_dict(
            global_counts=_make_global_counts(obs=0),
            database_size_bytes=1_000_000,
            backfill_progress={"planned_total": 0, "planned_completed": 0},
            active_settings=_make_settings(),
            ct_log_progress={"planned_total": 100_000, "planned_completed": 0},
        )
        assert result["status"] == "available"

    def test_ct_log_tree_size_basis_is_true_when_fallback_used(self) -> None:
        result = build_projection_dict(
            global_counts=_make_global_counts(obs=0),
            database_size_bytes=1_000_000,
            backfill_progress={"planned_total": 0, "planned_completed": 0},
            active_settings=_make_settings(),
            ct_log_progress={"planned_total": 100_000, "planned_completed": 0},
        )
        assert result.get("ct_log_tree_size_basis") is True

    def test_obs_count_zero_does_not_raise(self) -> None:
        """obs_count=0 on fresh install must not cause division by zero or crash."""
        result = build_projection_dict(
            global_counts=_make_global_counts(obs=0),
            database_size_bytes=500_000,
            backfill_progress={"planned_total": 0, "planned_completed": 0},
            active_settings=None,
            ct_log_progress={"planned_total": 50_000, "planned_completed": 0},
        )
        assert result["status"] == "available"

    def test_both_sources_zero_yields_insufficient_plan(self) -> None:
        result = build_projection_dict(
            global_counts=_make_global_counts(obs=0),
            database_size_bytes=100,
            backfill_progress={"planned_total": 0, "planned_completed": 0},
            active_settings=None,
            ct_log_progress={"planned_total": 0, "planned_completed": 0},
        )
        assert result["status"] == "insufficient_backfill_plan"

    def test_no_ct_log_progress_and_empty_backfill_yields_insufficient_plan(
        self,
    ) -> None:
        result = build_projection_dict(
            global_counts=_make_global_counts(obs=0),
            database_size_bytes=100,
            backfill_progress={"planned_total": 0, "planned_completed": 0},
            active_settings=None,
            ct_log_progress=None,
        )
        assert result["status"] == "insufficient_backfill_plan"


class TestBuildProjectionDictBackfillPreferred:
    """Backfill ranges take precedence over CT log progress when non-zero."""

    def test_backfill_basis_is_false_when_backfill_used(self) -> None:
        result = build_projection_dict(
            global_counts=_make_global_counts(obs=500),
            database_size_bytes=5_000_000,
            backfill_progress={"planned_total": 20_000, "planned_completed": 500},
            active_settings=None,
            ct_log_progress={"planned_total": 999_999, "planned_completed": 0},
        )
        assert result["status"] == "available"
        assert result.get("ct_log_tree_size_basis") is False

    def test_planned_total_matches_backfill_not_ct_log(self) -> None:
        result = build_projection_dict(
            global_counts=_make_global_counts(obs=100),
            database_size_bytes=1_000_000,
            backfill_progress={"planned_total": 20_000, "planned_completed": 1_000},
            active_settings=None,
            ct_log_progress={"planned_total": 999_000, "planned_completed": 0},
        )
        assert result["planned_observations_total"] == 20_000


class TestBuildProjectionDictNormalPath:
    """build_projection_dict returns expected fields on a normal ingesting system."""

    def test_returns_available_status_with_observations(self) -> None:
        result = build_projection_dict(
            global_counts=_make_global_counts(obs=10_000),
            database_size_bytes=50_000_000,
            backfill_progress={"planned_total": 500_000, "planned_completed": 10_000},
            active_settings=None,
            ct_log_progress=None,
        )
        assert result["status"] == "available"

    def test_projected_final_is_positive(self) -> None:
        result = build_projection_dict(
            global_counts=_make_global_counts(obs=10_000),
            database_size_bytes=50_000_000,
            backfill_progress={"planned_total": 500_000, "planned_completed": 10_000},
            active_settings=None,
            ct_log_progress=None,
        )
        assert result.get("projected_final_database_size_bytes", 0) > 0

    def test_confidence_field_is_present(self) -> None:
        result = build_projection_dict(
            global_counts=_make_global_counts(obs=1),
            database_size_bytes=1_000,
            backfill_progress={"planned_total": 100, "planned_completed": 1},
            active_settings=None,
            ct_log_progress=None,
        )
        assert "confidence" in result
