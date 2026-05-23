"""Tests for sarif_gate_cva.py."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from sarif_gate_cva import (
    Finding,
    _parse_message,
    categorize,
    load_findings,
    run_gate,
    write_summary,
)


class TestParseMessage:
    def test_extracts_key_value_fields(self):
        text = "Package: libfoo\nInstalled Version: 1.0.0\nFixed Version: 1.0.1\n"
        fields = _parse_message(text)
        assert fields["Package"] == "libfoo"
        assert fields["Installed Version"] == "1.0.0"
        assert fields["Fixed Version"] == "1.0.1"

    def test_extracts_url(self):
        text = "Severity: HIGH\n(https://nvd.nist.gov/vuln/detail/CVE-0)"
        fields = _parse_message(text)
        assert fields["url"] == "https://nvd.nist.gov/vuln/detail/CVE-0"

    def test_url_absent_defaults_to_empty(self):
        fields = _parse_message("Severity: LOW\n")
        assert fields["url"] == ""

    def test_empty_text_returns_only_url_key(self):
        fields = _parse_message("")
        assert fields == {"url": ""}


class TestLoadFindings:
    def test_returns_empty_list_for_missing_file(self, tmp_path):
        result = load_findings(str(tmp_path / "no.sarif"), str(tmp_path / "no2.sarif"))
        assert result == []

    def test_returns_empty_list_for_empty_file(self, tmp_path):
        p = tmp_path / "empty.sarif"
        p.write_text("", encoding="utf-8")
        assert load_findings(str(p), str(p)) == []

    def test_merges_api_and_app_findings(self, trivy_api_path, trivy_app_path):
        findings = load_findings(trivy_api_path, trivy_app_path)
        images = {f.image for f in findings}
        assert "API" in images
        assert "App" in images

    def test_api_findings_labelled_api(self, trivy_api_path, clean_trivy_path):
        findings = load_findings(trivy_api_path, clean_trivy_path)
        assert all(f.image == "API" for f in findings)

    def test_app_findings_labelled_app(self, clean_trivy_path, trivy_app_path):
        findings = load_findings(clean_trivy_path, trivy_app_path)
        assert all(f.image == "App" for f in findings)

    def test_skips_results_with_unrecognised_level(self, tmp_path):
        data = {
            "runs": [
                {
                    "results": [
                        {"ruleId": "R1", "level": "unknown", "message": {"text": ""}}
                    ]
                }
            ]
        }
        p = tmp_path / "x.sarif"
        p.write_text(json.dumps(data), encoding="utf-8")
        assert load_findings(str(p), str(p)) == []


class TestCategorize:
    def _finding(self, level: str, fixed: str = "") -> Finding:
        return Finding("API", "CVE-0", "HIGH", "pkg", "1.0", fixed, "", level)

    def test_error_with_fix_goes_to_blocking(self):
        f = self._finding("error", fixed="1.1")
        b, u, m, low = categorize([f])
        assert b == [f] and u == [] and m == [] and low == []

    def test_error_without_fix_goes_to_unpatched(self):
        f = self._finding("error", fixed="")
        b, u, m, low = categorize([f])
        assert b == [] and u == [f]

    def test_warning_goes_to_medium(self):
        f = self._finding("warning")
        b, u, m, low = categorize([f])
        assert m == [f]

    def test_note_goes_to_low(self):
        f = self._finding("note")
        b, u, m, low = categorize([f])
        assert low == [f]

    def test_empty_input_returns_four_empty_lists(self):
        assert categorize([]) == ([], [], [], [])


class TestRunGate:
    def _f(self, level: str = "error", fixed: str = "1.1") -> Finding:
        return Finding("API", "CVE-0", "HIGH", "pkg", "1.0", fixed, "", level)

    def test_returns_0_when_no_findings(self):
        assert run_gate([], [], [], []) == 0

    def test_returns_0_for_unpatched_only(self):
        unpatched = [self._f("error", fixed="")]
        assert run_gate([], unpatched, [], []) == 0

    def test_returns_1_when_blocking_present(self):
        blocking = [self._f("error", fixed="1.1")]
        assert run_gate(blocking, [], [], []) == 1

    def test_prints_fail_message_on_blocking(self, capsys):
        blocking = [self._f("error", fixed="1.1")]
        run_gate(blocking, [], [], [])
        assert "FAIL" in capsys.readouterr().out

    def test_prints_ok_message_on_pass(self, capsys):
        run_gate([], [], [], [])
        assert "OK" in capsys.readouterr().out

    def test_informational_findings_printed_on_pass(self, capsys):
        medium = [self._f("warning", fixed="")]
        run_gate([], [], medium, [])
        assert "OK" in capsys.readouterr().out


class TestWriteSummary:
    def _f(self, level: str = "error", fixed: str = "1.1") -> Finding:
        return Finding(
            "API",
            "CVE-2024-001",
            "HIGH",
            "libfoo",
            "1.0",
            fixed,
            "https://example.com",
            level,
        )

    def test_writes_pass_heading_when_no_blocking(self, tmp_path, monkeypatch):
        summary = tmp_path / "summary.md"
        summary.write_text("", encoding="utf-8")
        monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
        write_summary([], [], [], [])
        assert "✅" in summary.read_text()

    def test_writes_fail_heading_when_blocking(self, tmp_path, monkeypatch):
        summary = tmp_path / "summary.md"
        summary.write_text("", encoding="utf-8")
        monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
        write_summary([self._f()], [], [], [])
        content = summary.read_text()
        assert "⛔" in content
        assert "CVE-2024-001" in content

    def test_no_error_when_env_var_unset(self, monkeypatch):
        monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
        write_summary([], [], [], [])  # must not raise

    def test_unpatched_rendered_in_details_block(self, tmp_path, monkeypatch):
        summary = tmp_path / "summary.md"
        summary.write_text("", encoding="utf-8")
        monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
        write_summary([], [self._f("error", fixed="")], [], [])
        assert "<details>" in summary.read_text()

    def test_cve_link_rendered_when_url_present(self, tmp_path, monkeypatch):
        summary = tmp_path / "summary.md"
        summary.write_text("", encoding="utf-8")
        monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
        write_summary([self._f()], [], [], [])
        assert "https://example.com" in summary.read_text()
