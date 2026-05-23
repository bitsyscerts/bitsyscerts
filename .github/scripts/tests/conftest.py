"""Shared SARIF fixtures for .github/scripts tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest


def _sarif(results: list[dict]) -> dict:
    return {"runs": [{"results": results}]}


def _result(
    rule_id: str = "TEST001",
    level: str = "note",
    message: str = "Test finding",
) -> dict:
    return {"ruleId": rule_id, "level": level, "message": {"text": message}}


def _trivy_result(
    rule_id: str = "CVE-2024-0001",
    level: str = "error",
    package: str = "libfoo",
    installed: str = "1.0.0",
    fixed: str = "1.0.1",
    severity: str = "HIGH",
) -> dict:
    msg = (
        f"Package: {package}\n"
        f"Installed Version: {installed}\n"
        f"Fixed Version: {fixed}\n"
        f"Severity: {severity}\n"
        "(https://nvd.nist.gov/vuln/detail/{rule_id})"
    )
    return {"ruleId": rule_id, "level": level, "message": {"text": msg}}


@pytest.fixture()
def sarif_path(tmp_path: Path):
    """Factory: write a SARIF dict to a temp file and return its path string."""

    def _write(data: dict) -> str:
        p = tmp_path / "test.sarif"
        p.write_text(json.dumps(data), encoding="utf-8")
        return str(p)

    return _write


@pytest.fixture()
def clean_sarif(sarif_path):
    return sarif_path(_sarif([]))


@pytest.fixture()
def error_sarif(sarif_path):
    return sarif_path(
        _sarif([_result(level="error", rule_id="SEC001", message="Injected value")])
    )


@pytest.fixture()
def mixed_sarif(sarif_path):
    return sarif_path(
        _sarif(
            [
                _result(level="error", rule_id="SEC001", message="Critical issue"),
                _result(level="warning", rule_id="SEC002", message="Medium issue"),
                _result(level="note", rule_id="SEC003", message="Low issue"),
            ]
        )
    )


@pytest.fixture()
def trivy_api_path(tmp_path: Path):
    data = _sarif(
        [
            _trivy_result(rule_id="CVE-2024-0001", level="error", fixed="1.0.1"),
            _trivy_result(
                rule_id="CVE-2024-0002", level="error", fixed="", package="libbar"
            ),
            _trivy_result(
                rule_id="CVE-2024-0003", level="warning", fixed="", severity="MEDIUM"
            ),
        ]
    )
    p = tmp_path / "trivy-api.sarif"
    p.write_text(json.dumps(data), encoding="utf-8")
    return str(p)


@pytest.fixture()
def trivy_app_path(tmp_path: Path):
    data = _sarif(
        [
            _trivy_result(
                rule_id="CVE-2024-0004",
                level="note",
                fixed="",
                severity="LOW",
                package="libbaz",
            ),
        ]
    )
    p = tmp_path / "trivy-app.sarif"
    p.write_text(json.dumps(data), encoding="utf-8")
    return str(p)


@pytest.fixture()
def clean_trivy_path(tmp_path: Path):
    p = tmp_path / "trivy-clean.sarif"
    p.write_text(json.dumps(_sarif([])), encoding="utf-8")
    return str(p)
