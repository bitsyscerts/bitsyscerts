#!/usr/bin/env python3
"""Inject stable fingerprints into a SARIF file for consistent deduplication.

Reads *--sarif*, stamps each result with a SHA-256 ``stableResultHash``
under ``partialFingerprints``, then writes the file back in place.

Usage::

    sarif_normalize.py --sarif <file> --label <label>
    sarif_normalize.py --sarif <file> --label <label> --trivy
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def _seed_standard(result: dict, label: str) -> str:
    """Fingerprint seed for text-only SAST/SCA results."""
    msg = result.get("message", {}).get("text", "").partition("\n")[0]
    return "|".join(
        [label, result.get("ruleId", "?"), result.get("level", "note"), msg]
    )


def _seed_trivy(result: dict, label: str) -> str:
    """Fingerprint seed for Trivy's package-aware results."""
    msg = result.get("message", {}).get("text", "")
    fields: dict[str, str] = {
        "Package": "",
        "Installed Version": "",
        "Fixed Version": "",
    }
    for line in msg.splitlines():
        for key in fields:
            if line.startswith(f"{key}: "):
                fields[key] = line.split(": ", 1)[1].strip()
    return "|".join(
        [
            label,
            result.get("ruleId", "?"),
            result.get("level", "note"),
            fields["Package"],
            fields["Installed Version"],
            fields["Fixed Version"],
        ]
    )


def normalize(path: str, label: str, *, trivy: bool = False) -> None:
    """Stamp each result in *path* with a stable SHA-256 fingerprint."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    seed_fn = _seed_trivy if trivy else _seed_standard
    for run in data.get("runs", []):
        for result in run.get("results", []):
            seed = seed_fn(result, label)
            fp = hashlib.sha256(seed.encode("utf-8")).hexdigest()
            result.setdefault("partialFingerprints", {})["stableResultHash"] = fp
    Path(path).write_text(json.dumps(data), encoding="utf-8")


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--sarif", required=True, help="Path to SARIF file (modified in place)"
    )
    p.add_argument("--label", required=True, help='Source label, e.g. "sast-semgrep"')
    p.add_argument(
        "--trivy", action="store_true", help="Use package-aware fingerprinting"
    )
    return p


def main() -> None:
    args = _build_parser().parse_args()
    normalize(args.sarif, args.label, trivy=args.trivy)
    print(f"Fingerprints written: {args.sarif}")


if __name__ == "__main__":
    main()
