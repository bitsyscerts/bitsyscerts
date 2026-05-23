#!/usr/bin/env python3
"""Severity gate for container vulnerability SARIF files (Trivy).

Gate logic: fail only when ERROR-level findings have a fix available.
Unpatched HIGH/CRITICAL findings are surfaced but do not block the build.
Writes a markdown block to ``$GITHUB_STEP_SUMMARY``.

Usage::

    sarif_gate_cva.py --api trivy-api.sarif --app trivy-app.sarif
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import NamedTuple


class Finding(NamedTuple):
    image: str
    cve: str
    severity: str
    package: str
    installed: str
    fixed: str
    url: str
    level: str


def _parse_message(text: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for line in text.splitlines():
        if ": " in line:
            k, _, v = line.partition(": ")
            fields[k.strip()] = v.strip()
    m = re.search(r"\(https?://[^)]+\)", text)
    fields["url"] = m.group(0)[1:-1] if m else ""
    return fields


def _load_sarif(fname: str, label: str) -> list[Finding]:
    """Parse one Trivy SARIF file into a flat list of Finding objects."""
    p = Path(fname)
    if not p.exists() or p.stat().st_size == 0:
        print(f"WARN: {fname} missing or empty -- scan may have errored")
        return []
    data = json.loads(p.read_text(encoding="utf-8"))
    results: list[Finding] = []
    for run in data.get("runs", []):
        for r in run.get("results", []):
            if r.get("level") not in ("error", "warning", "note"):
                continue
            f = _parse_message(r.get("message", {}).get("text", ""))
            results.append(
                Finding(
                    image=label,
                    cve=r.get("ruleId", "?"),
                    severity=f.get("Severity", "?"),
                    package=f.get("Package", "?"),
                    installed=f.get("Installed Version", "?"),
                    fixed=f.get("Fixed Version", ""),
                    url=f.get("url", ""),
                    level=r.get("level", "note"),
                )
            )
    return results


def load_findings(api_sarif: str, app_sarif: str) -> list[Finding]:
    """Merge findings from both container image SARIF files."""
    return _load_sarif(api_sarif, "API") + _load_sarif(app_sarif, "App")


def categorize(
    findings: list[Finding],
) -> tuple[list[Finding], list[Finding], list[Finding], list[Finding]]:
    """Split findings into (blocking, unpatched, medium, low)."""
    blocking = [f for f in findings if f.level == "error" and f.fixed]
    unpatched = [f for f in findings if f.level == "error" and not f.fixed]
    medium = [f for f in findings if f.level == "warning"]
    low = [f for f in findings if f.level == "note"]
    return blocking, unpatched, medium, low


def _md_row(f: Finding, *, show_fixed: bool) -> str:
    cve = f"[{f.cve}]({f.url})" if f.url else f.cve
    base = f"| {f.image} | {cve} | **{f.severity}** | `{f.package}` | `{f.installed}`"
    return base + (f" | `{f.fixed}` |\n" if show_fixed else " |\n")


def _write_blocking(fh, blocking: list[Finding]) -> None:
    if blocking:
        fh.write(f"## ⛔ CVA — {len(blocking)} HIGH/CRITICAL with fix available\n\n")
        fh.write("|Image|CVE|Sev|Package|Installed|Fix|\n|---|---|---|---|---|---|\n")
        for f in blocking:
            fh.write(_md_row(f, show_fixed=True))
        fh.write(
            "\n> Upgrade the package(s) above in the relevant Dockerfile to clear this gate.\n\n"
        )
    else:
        fh.write("## ✅ CVA — no actionable HIGH/CRITICAL findings\n\n")


def _write_detail(
    fh, icon: str, label: str, findings: list[Finding], *, show_fixed: bool
) -> None:
    if not findings:
        return
    cols = (
        "|Image|CVE|Sev|Package|Installed|Fix|\n|---|---|---|---|---|---|\n"
        if show_fixed
        else "|Image|CVE|Sev|Package|Installed|\n|---|---|---|---|---|\n"
    )
    fh.write(
        f"<details><summary>{icon} {len(findings)} {label} (not blocking)</summary>\n\n"
    )
    fh.write(cols)
    for f in findings:
        fh.write(_md_row(f, show_fixed=show_fixed))
    fh.write("\n</details>\n\n")


def write_summary(
    blocking: list[Finding],
    unpatched: list[Finding],
    medium: list[Finding],
    low: list[Finding],
) -> None:
    """Append a markdown summary block to ``$GITHUB_STEP_SUMMARY``."""
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not path:
        return
    with open(path, "a", encoding="utf-8") as fh:
        _write_blocking(fh, blocking)
        _write_detail(
            fh, "⚠️", "HIGH/CRITICAL unpatched (no fix yet)", unpatched, show_fixed=False
        )
        _write_detail(fh, "ℹ️", "MEDIUM findings", medium, show_fixed=True)
        _write_detail(fh, "ℹ️", "LOW findings", low, show_fixed=True)


def _print_table(label: str, findings: list[Finding]) -> None:
    if not findings:
        return
    widths = (5, 20, 8, 30, 22, 14)
    cols = ("IMAGE", "CVE", "SEV", "PACKAGE", "INSTALLED", "FIX AVAILABLE")
    fmt = "  ".join(f"{{:<{w}}}" for w in widths)
    print(f"\n  {label}:")
    print(fmt.format(*cols))
    print("  ".join("-" * w for w in widths))
    for f in findings:
        print(
            fmt.format(
                f.image,
                f.cve,
                f.severity,
                f.package[: widths[3]],
                f.installed,
                f.fixed or "none yet",
            )
        )


def run_gate(
    blocking: list[Finding],
    unpatched: list[Finding],
    medium: list[Finding],
    low: list[Finding],
) -> int:
    """Print result and return exit code (0 = pass, 1 = fail)."""
    if blocking:
        print(f"FAIL — {len(blocking)} HIGH/CRITICAL finding(s) with fix available:\n")
        _print_table("BLOCKING", blocking)
        _print_table("UNPATCHED HIGH/CRITICAL (informational)", unpatched)
        _print_table("MEDIUM (informational)", medium)
        _print_table("LOW (informational)", low)
        return 1
    if unpatched or medium or low:
        print("OK — no blocking CVEs. Informational findings below:")
        _print_table("UNPATCHED HIGH/CRITICAL", unpatched)
        _print_table("MEDIUM", medium)
        _print_table("LOW", low)
    else:
        print("OK: no vulnerabilities found in container images")
    return 0


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--api", required=True, help="Path to Trivy API SARIF")
    p.add_argument("--app", required=True, help="Path to Trivy App SARIF")
    args = p.parse_args()
    findings = load_findings(args.api, args.app)
    blocking, unpatched, medium, low = categorize(findings)
    write_summary(blocking, unpatched, medium, low)
    sys.exit(run_gate(blocking, unpatched, medium, low))


if __name__ == "__main__":
    main()
