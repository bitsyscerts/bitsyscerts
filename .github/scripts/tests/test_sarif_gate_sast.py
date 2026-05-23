"""Tests for sarif_gate_sast.py."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from sarif_gate_sast import load_findings, run_gate, write_summary


class TestLoadFindings:
    def test_returns_none_for_missing_file(self, tmp_path):
        result = load_findings(str(tmp_path / "nonexistent.sarif"))
        assert result is None

    def test_returns_none_for_empty_file(self, tmp_path):
        p = tmp_path / "empty.sarif"
        p.write_text("", encoding="utf-8")
        assert load_findings(str(p)) is None

    def test_clean_sarif_returns_empty_buckets(self, clean_sarif):
        rows = load_findings(clean_sarif)
        assert rows is not None
        assert rows == {"error": [], "warning": [], "note": []}

    def test_error_findings_placed_in_error_bucket(self, error_sarif):
        rows = load_findings(error_sarif)
        assert len(rows["error"]) == 1
        assert rows["error"][0]["id"] == "SEC001"

    def test_mixed_findings_split_correctly(self, mixed_sarif):
        rows = load_findings(mixed_sarif)
        assert len(rows["error"]) == 1
        assert len(rows["warning"]) == 1
        assert len(rows["note"]) == 1

    def test_message_truncated_to_first_line(self, sarif_path):
        import json

        path = sarif_path(
            {
                "runs": [
                    {
                        "results": [
                            {
                                "ruleId": "R1",
                                "level": "error",
                                "message": {"text": "first line\nsecond line"},
                            }
                        ]
                    }
                ]
            }
        )
        rows = load_findings(path)
        assert rows["error"][0]["msg"] == "first line"

    def test_unknown_level_is_skipped(self, sarif_path):
        import json

        path = sarif_path(
            {
                "runs": [
                    {
                        "results": [
                            {
                                "ruleId": "R1",
                                "level": "unknown_level",
                                "message": {"text": "msg"},
                            }
                        ]
                    }
                ]
            }
        )
        rows = load_findings(path)
        assert rows == {"error": [], "warning": [], "note": []}


class TestRunGate:
    def test_returns_0_when_no_errors(self):
        rows = {"error": [], "warning": [], "note": []}
        assert run_gate(rows, "SAST") == 0

    def test_returns_1_when_errors_present(self):
        rows = {"error": [{"id": "R1", "msg": "bad"}], "warning": [], "note": []}
        assert run_gate(rows, "SAST") == 1

    def test_returns_0_with_warnings_only(self):
        rows = {"error": [], "warning": [{"id": "R2", "msg": "warn"}], "note": []}
        assert run_gate(rows, "SCA") == 0

    def test_prints_finding_ids_on_failure(self, capsys):
        rows = {
            "error": [{"id": "SEC001", "msg": "injection"}],
            "warning": [],
            "note": [],
        }
        run_gate(rows, "SAST")
        captured = capsys.readouterr()
        assert "SEC001" in captured.out

    def test_caps_output_at_20_findings(self, capsys):
        errors = [{"id": f"R{i}", "msg": "m"} for i in range(25)]
        rows = {"error": errors, "warning": [], "note": []}
        run_gate(rows, "SAST")
        captured = capsys.readouterr()
        # Only first 20 should be printed
        assert "R19" in captured.out
        assert "R20" not in captured.out


class TestWriteSummary:
    def test_writes_pass_heading_when_no_errors(self, tmp_path, monkeypatch):
        summary = tmp_path / "summary.md"
        summary.write_text("", encoding="utf-8")
        monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
        write_summary("SAST", {"error": [], "warning": [], "note": []})
        content = summary.read_text()
        assert "✅" in content
        assert "no HIGH/CRITICAL" in content

    def test_writes_fail_heading_when_errors_present(self, tmp_path, monkeypatch):
        summary = tmp_path / "summary.md"
        summary.write_text("", encoding="utf-8")
        monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
        write_summary(
            "SAST", {"error": [{"id": "R1", "msg": "bad"}], "warning": [], "note": []}
        )
        content = summary.read_text()
        assert "⛔" in content
        assert "R1" in content

    def test_no_error_when_env_var_unset(self, monkeypatch):
        monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
        write_summary("SCA", {"error": [], "warning": [], "note": []})  # must not raise

    def test_warning_findings_appear_in_details_block(self, tmp_path, monkeypatch):
        summary = tmp_path / "summary.md"
        summary.write_text("", encoding="utf-8")
        monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
        write_summary(
            "SCA", {"error": [], "warning": [{"id": "W1", "msg": "medium"}], "note": []}
        )
        content = summary.read_text()
        assert "<details>" in content
        assert "W1" in content
