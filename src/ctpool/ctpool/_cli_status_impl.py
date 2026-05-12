"""``ctpool status`` — concise operator truth from the latest stats snapshot.

This command intentionally does **not** run any heavy live queries.  It
reads the most recent ``ct_stats_snapshots`` row and renders a small
text summary so an operator can answer in one glance:

* Are stats fresh, or stale, or missing?
* Are workers alive?
* Is backfill moving?
* Is ingestion producing new unique records, or mostly duplicates?
* Is the active storage profile being enforced by maintenance?

When the snapshot is missing or unreadable, we print a clear message
instead of hammering the database.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from rich.console import Console

from ctpool.config import Settings
from ctpool.db import create_engine, create_session_factory
from ctpool.stats_snapshot_repository import StatsSnapshotRepository

_SNAPSHOT_TYPE = "full"


async def run_status(
    *,
    settings: Settings,
    stale_threshold_seconds: int,
    console: Console,
) -> None:
    """Render the operator status line by line from the latest snapshot.

    Args:
        settings: ``ctpool`` runtime settings.
        stale_threshold_seconds: Snapshot age above which we mark stats
            stale.  Mirrors the API ``stats_stale_seconds`` setting.
        console: Rich console used for output.
    """
    engine = create_engine(settings)
    factory = create_session_factory(engine)
    repo = StatsSnapshotRepository()

    try:
        async with factory() as session:
            payload = await repo.get_latest_snapshot(session, _SNAPSHOT_TYPE)
            age = await repo.get_latest_snapshot_age_seconds(session, _SNAPSHOT_TYPE)
    finally:
        await engine.dispose()

    console.print("[bold]BitsysCerts Status[/bold]")
    console.print("")
    _print_freshness(console, age=age, threshold=stale_threshold_seconds)

    if payload is None:
        console.print(
            "[yellow]No stats snapshot is available.  "
            "Run `ctpool stats-snapshot --once` to generate one.[/yellow]"
        )
        return

    _print_storage_profile(console, payload)
    _print_workers(console, payload)
    _print_backfill(console, payload)
    _print_tail(console, payload)
    _print_ingestion(console, payload)
    _print_maintenance(console, payload)


def _print_freshness(console: Console, *, age: float | None, threshold: int) -> None:
    """Render a single line describing snapshot age and staleness."""
    if age is None:
        console.print("[yellow]Stats snapshot: missing[/yellow]")
        return
    is_stale = age > threshold
    age_s = int(age)
    label = "[red]stale[/red]" if is_stale else "[green]fresh[/green]"
    console.print(f"Stats snapshot: {label}, generated {age_s}s ago")


def _print_storage_profile(console: Console, payload: dict[str, Any]) -> None:
    """Render the active storage profile and whether maintenance enforces it."""
    profile = payload.get("storage_profile") or {}
    name = profile.get("storage_profile") if isinstance(profile, dict) else None
    maint = payload.get("maintenance") or {}
    enforced = bool(maint.get("is_enforced")) if isinstance(maint, dict) else False
    enforced_label = (
        "[green]enforced[/green]" if enforced else "[yellow]not enforced[/yellow]"
    )
    console.print(f"Storage profile: {name or 'unknown'}, {enforced_label}")


def _print_workers(console: Console, payload: dict[str, Any]) -> None:
    """Render worker counts."""
    workers = payload.get("workers") or {}
    if not isinstance(workers, dict):
        return
    items = workers.get("items") or []
    active = sum(1 for w in items if isinstance(w, dict) and w.get("is_active"))
    stale = workers.get("stale_count") or 0
    console.print(f"Workers: {active} active, {stale} stale")


def _print_backfill(console: Console, payload: dict[str, Any]) -> None:
    """Render the per-log backfill state summary."""
    state = payload.get("backfill_state") or {}
    if not isinstance(state, dict):
        return
    counts = state.get("status_counts") or {}
    if not isinstance(counts, dict):
        return
    parts = []
    for key in ("processing", "retrying", "rate_limited", "paused", "complete"):
        if key in counts:
            parts.append(f"{int(counts[key])} {key}")
    if parts:
        console.print(f"Backfill: {', '.join(parts)}")


def _print_tail(console: Console, payload: dict[str, Any]) -> None:
    """Render tail freshness summary."""
    freshness = payload.get("tail_freshness") or {}
    if not isinstance(freshness, dict):
        return
    stale = int(freshness.get("stale_log_count") or 0)
    oldest = freshness.get("oldest_lag_seconds")
    if oldest is None:
        console.print(f"Tail: {stale} stale logs")
    else:
        console.print(f"Tail: {stale} stale logs, oldest lag {int(oldest)}s")


def _print_ingestion(console: Console, payload: dict[str, Any]) -> None:
    """Render ingestion throughput, uniqueness, and error rates."""
    rate = payload.get("ingestion_rate") or {}
    windows = rate.get("windows") if isinstance(rate, dict) else None
    if not windows or not isinstance(windows, list):
        return
    # Pick the shortest window for "current" feel.
    win = min(windows, key=lambda w: w.get("window_seconds", 99999))
    obs_per_min = win.get("observations_per_min") or (
        (win.get("observations_per_sec") or 0) * 60
    )
    certs = win.get("certificates_parsed_per_min") or win.get("certs_per_min") or 0
    hosts = win.get("hostnames_observed_per_min") or win.get("hostnames_per_min") or 0
    console.print("Ingestion:")
    console.print(f"  observations/min:      {_fmt_rate(obs_per_min)}")
    console.print(f"  certs parsed/min:      {_fmt_rate(certs)}")
    console.print(f"  hostnames observed/min:{_fmt_rate(hosts)}")

    new_certs = win.get("new_unique_certificates_per_min")
    duplicate_certs = win.get("duplicate_certificates_per_min")
    new_hosts = win.get("new_unique_hostnames_per_min")
    known_hosts = win.get("known_hostnames_per_min")
    if None in (new_certs, duplicate_certs, new_hosts, known_hosts):
        console.print("  uniqueness metrics unavailable")
    else:
        console.print(f"  new certs/min:         {_fmt_rate(new_certs)}")
        console.print(f"  duplicate certs/min:   {_fmt_rate(duplicate_certs)}")
        console.print(f"  new hostnames/min:     {_fmt_rate(new_hosts)}")
        console.print(f"  known hostnames/min:   {_fmt_rate(known_hosts)}")

    retryable = win.get("retryable_errors_per_min")
    terminal = win.get("terminal_entry_errors_per_min")
    if retryable is not None or terminal is not None:
        console.print("Errors:")
        console.print(f"  retryable/min:         {_fmt_rate(retryable or 0)}")
        console.print(f"  terminal entries/min:  {_fmt_rate(terminal or 0)}")


def _print_maintenance(console: Console, payload: dict[str, Any]) -> None:
    """Render the most recent retention maintenance result."""
    maint = payload.get("maintenance") or {}
    if not isinstance(maint, dict):
        return
    status = maint.get("last_prune_status")
    completed_at = maint.get("last_prune_completed_at")
    if status is None and completed_at is None:
        console.print("Maintenance: never run")
        return
    label = status or "unknown"
    if completed_at:
        age = _age_iso(completed_at)
        if age is not None:
            console.print(f"Maintenance: last prune {label} {age}")
            return
    console.print(f"Maintenance: last prune {label}")


def _age_iso(value: str) -> str | None:
    """Render a human-readable age (e.g. ``12m ago``) for an ISO datetime string."""
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None
    secs = int((datetime.now(UTC) - dt).total_seconds())
    if secs < 60:
        return f"{secs}s ago"
    if secs < 3600:
        return f"{secs // 60}m ago"
    return f"{secs // 3600}h ago"


def _fmt_rate(value: float | int) -> str:
    """Format a per-minute rate for operator-facing text output."""
    return f"{int(round(float(value))):,}"
