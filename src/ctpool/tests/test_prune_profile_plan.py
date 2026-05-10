"""Tests for ctpool.prune_profile_plan."""

from __future__ import annotations

from datetime import UTC, datetime

from ctpool.prune_profile_plan import (
    PruneAggregate,
    PruneCategory,
    build_prune_plan,
    summarize_plan_as_json,
    summarize_plan_for_console,
)


def _make_aggregate(
    metrics_days: int = 14, observation_days: int = 7
) -> PruneAggregate:
    return build_prune_plan(
        storage_profile="lite",
        cert_storage_mode="metadata",
        hostname_retention_mode="current",
        cert_retention_days=7,
        observation_retention_days=observation_days,
        entry_outcome_retention_days=7,
        metrics_retention_days=metrics_days,
        started_at=datetime.now(UTC),
        mode="dry_run",
    )


class TestPruneCategory:
    def test_is_disabled_when_retention_zero(self) -> None:
        assert PruneCategory(name="ingestion_metrics", retention_days=0).is_disabled

    def test_is_enabled_when_retention_positive(self) -> None:
        assert not PruneCategory(
            name="ingestion_metrics", retention_days=14
        ).is_disabled


class TestBuildPrunePlan:
    def test_builds_four_categories(self) -> None:
        plan = _make_aggregate()
        names = [c.name for c in plan.categories]
        assert sorted(names) == sorted(
            [
                "certificates",
                "observations",
                "entry_outcomes",
                "ingestion_metrics",
            ]
        )

    def test_disabled_category_is_marked(self) -> None:
        plan = _make_aggregate(metrics_days=0)
        metrics = next(c for c in plan.categories if c.name == "ingestion_metrics")
        assert metrics.is_disabled

    def test_mode_is_propagated(self) -> None:
        plan = _make_aggregate()
        assert plan.mode == "dry_run"


class TestSummarizers:
    def test_console_summary_includes_profile(self) -> None:
        plan = _make_aggregate()
        lines = summarize_plan_for_console(plan)
        joined = "\n".join(lines)
        assert "lite" in joined.lower()

    def test_console_summary_warns_about_disabled(self) -> None:
        plan = _make_aggregate(metrics_days=0)
        joined = "\n".join(summarize_plan_for_console(plan))
        assert "indefinitely" in joined.lower()

    def test_json_summary_is_serialisable(self) -> None:
        import json as _json

        plan = _make_aggregate()
        payload = summarize_plan_as_json(plan)
        # Should round-trip via json without exceptions.
        _json.dumps(payload, default=str)
        assert payload["storage_profile"] == "lite"

    def test_aggregate_dict_round_trip(self) -> None:
        plan = _make_aggregate()
        d = plan.as_serialisable_dict()
        assert d["mode"] == "dry_run"
        assert isinstance(d["categories"], list)
