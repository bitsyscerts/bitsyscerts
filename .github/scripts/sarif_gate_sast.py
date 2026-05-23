#!/usr/bin/env python3
"""Severity gate for SAST/SCA SARIF files (Semgrep, OSV Scanner).

Fails with exit code 1 when ERROR-level findings exist.
Writes a markdown block to ``$GITHUB_STEP_SUMMARY``.

Usage::

    sarif_gate_sast.py --sarif <file> --tool sast
    sarif_gate_sast.py --sarif <file> --tool sca
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

_TOOL_TITLES: dict[str, str] = {"sast": "SAST", "sca": "SCA"}
_COL_HEADERS = "|Rule|Details|\n|---|---|\n"


def load_findings(path: str) -> dict[str, list[dict]] | None:
    """Return findings grouped by level, or None if the file is absent/empty."""
    p = Path(path)
    if not p.exists() or p.stat().st_size == 0:
        print(f"WARN: {path} missing or empty")
        return None
    data = json.loads(p.read_text(encoding="utf-8"))
    rows: dict[str, list[dict]] = {"error": [], "warning": [], "note": []}
    for run in data.get("runs", []):
        for r in run.get("results", []):
            level = r.get("level", "note")
            if level not in rows:
                continue
            rows[level].append(
                {
                    "id": r.get("ruleId", "?"),
                    "msg": r.get("message", {}).get("text", "").partition("\n")[0],
                }
            )
    return rows


def _write_detail(fh, icon: str, label: str, rows: list[dict]) -> None:
    if not rows:
        return
    fh.write(
        f"<details><summary>{icon} {len(rows)} {label} (not blocking)</summary>\n\n"
    )
    fh.write(_COL_HEADERS)
    for r in rows:
        fh.write(f"| `{r['id']}` | {r['msg'][:150]} |\n")
    fh.write("\n</details>\n\n")


def write_summary(title: str, rows: dict[str, list[dict]]) -> None:
    """Append a markdown summary block to ``$GITHUB_STEP_SUMMARY``."""
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not summary_path:
        return
    errors, warnings, notes = rows["error"], rows["warning"], rows["note"]
    with open(summary_path, "a", encoding="utf-8") as fh:
        if errors:
            fh.write(f"## ⛔ {title} — {len(errors)} HIGH/CRITICAL finding(s)\n\n")
            fh.write(_COL_HEADERS)
            for r in errors:
                fh.write(f"| `{r['id']}` | {r['msg'][:150]} |\n")
            fh.write("\n> Fix the above finding(s) to clear this gate.\n\n")
        else:
            fh.write(f"## ✅ {title} — no HIGH/CRITICAL findings\n\n")
        _write_detail(fh, "⚠️", "MEDIUM findings", warnings)
        _write_detail(fh, "ℹ️", "LOW findings", notes)


def run_gate(rows: dict[str, list[dict]], title: str) -> int:
    """Print result and return exit code (0 = pass, 1 = fail)."""
    errors = rows["error"]
    if errors:
        print(f"FAIL — {len(errors)} HIGH/CRITICAL {title} finding(s):\n")
        for r in errors[:20]:
            print(f"  {r['id']}: {r['msg']}")
        return 1
    total = len(rows["warning"]) + len(rows["note"])
    if total:
        print(
            f"OK — no blocking findings. {total} informational finding(s) -- see step summary."
        )
    else:
        print(f"OK: no {title} findings")
    return 0


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--sarif", required=True)
    p.add_argument("--tool", required=True, choices=list(_TOOL_TITLES))
    args = p.parse_args()
    title = _TOOL_TITLES[args.tool]
    rows = load_findings(args.sarif)
    if rows is None:
        sys.exit(0)
    write_summary(title, rows)
    sys.exit(run_gate(rows, title))


if __name__ == "__main__":
    main()
