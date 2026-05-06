"""Render shared DB contention status for ctpool stats surfaces."""

from __future__ import annotations

from rich.panel import Panel

from ctpool.db_contention_types import DbContentionOperatorSnapshot


def render_db_contention_panel(snapshot: DbContentionOperatorSnapshot) -> Panel:
    """Return a Rich panel describing the current shared contention state."""
    lines = [
        f"[bold]Status:[/bold] {_colorize_status(snapshot.status)}",
        f"[bold]Shared pressure:[/bold] {snapshot.pressure_ema:.3f}",
        f"[bold]Base sleep:[/bold] {snapshot.base_sleep_seconds:.2f} s",
        "[bold]Effective batch cap:[/bold] "
        f"{_format_cap(snapshot.effective_batch_size_cap)}",
    ]
    if snapshot.updated_at is not None:
        lines.append(f"[bold]Updated:[/bold] {snapshot.updated_at.isoformat()}")
    if snapshot.notes:
        lines.append("")
        lines.extend(f"- {note}" for note in snapshot.notes)
    return Panel(
        "\n".join(lines),
        title="DB Contention Control",
        border_style="dim",
        expand=False,
    )


def _format_cap(value: int | None) -> str:
    if value is None:
        return "—"
    return f"{value:,}"


def _colorize_status(status: str) -> str:
    color = {
        "disabled": "yellow",
        "initializing": "cyan",
        "healthy": "green",
        "throttling": "yellow",
        "stale": "red",
    }.get(status, "white")
    return f"[{color}]{status}[/{color}]"
