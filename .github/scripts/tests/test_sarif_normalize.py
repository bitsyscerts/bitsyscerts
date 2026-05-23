"""Tests for sarif_normalize.py."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from sarif_normalize import _seed_standard, _seed_trivy, normalize


class TestSeedStandard:
    def test_includes_label(self):
        result = {"ruleId": "R1", "level": "error", "message": {"text": "msg"}}
        assert _seed_standard(result, "sast-semgrep").startswith("sast-semgrep|")

    def test_includes_rule_id(self):
        result = {"ruleId": "SEC001", "level": "error", "message": {"text": "msg"}}
        assert "SEC001" in _seed_standard(result, "label")

    def test_uses_first_line_of_message(self):
        result = {"ruleId": "R1", "level": "note", "message": {"text": "first\nsecond"}}
        seed = _seed_standard(result, "l")
        assert "first" in seed
        assert "second" not in seed

    def test_defaults_for_missing_fields(self):
        seed = _seed_standard({}, "lbl")
        assert seed == "lbl|?|note|"

    def test_deterministic(self):
        result = {"ruleId": "R1", "level": "error", "message": {"text": "msg"}}
        assert _seed_standard(result, "l") == _seed_standard(result, "l")

    def test_different_rules_produce_different_seeds(self):
        r1 = {"ruleId": "R1", "level": "error", "message": {"text": "msg"}}
        r2 = {"ruleId": "R2", "level": "error", "message": {"text": "msg"}}
        assert _seed_standard(r1, "l") != _seed_standard(r2, "l")


class TestSeedTrivy:
    def test_includes_package_fields(self):
        msg = "Package: libfoo\nInstalled Version: 1.0.0\nFixed Version: 1.0.1\n"
        result = {"ruleId": "CVE-0", "level": "error", "message": {"text": msg}}
        seed = _seed_trivy(result, "cva-trivy-api")
        assert "libfoo" in seed
        assert "1.0.0" in seed
        assert "1.0.1" in seed

    def test_missing_package_fields_default_to_empty(self):
        result = {"ruleId": "CVE-0", "level": "error", "message": {"text": "no fields"}}
        seed = _seed_trivy(result, "lbl")
        assert seed.endswith("|||")

    def test_differs_from_standard_for_same_result(self):
        msg = "Package: libfoo\nInstalled Version: 1.0\nFixed Version: 1.1\n"
        result = {"ruleId": "CVE-0", "level": "error", "message": {"text": msg}}
        assert _seed_trivy(result, "lbl") != _seed_standard(result, "lbl")

    def test_deterministic(self):
        msg = "Package: p\nInstalled Version: 1\nFixed Version: 2\n"
        result = {"ruleId": "CVE-0", "level": "error", "message": {"text": msg}}
        assert _seed_trivy(result, "l") == _seed_trivy(result, "l")


class TestNormalize:
    def test_writes_fingerprint_to_file(self, sarif_path):
        path = sarif_path(
            {
                "runs": [
                    {
                        "results": [
                            {"ruleId": "R1", "level": "error", "message": {"text": "m"}}
                        ]
                    }
                ]
            }
        )
        normalize(path, "sast-semgrep")
        data = json.loads(Path(path).read_text())
        fp = data["runs"][0]["results"][0]["partialFingerprints"]["stableResultHash"]
        assert len(fp) == 64  # SHA-256 hex

    def test_fingerprint_matches_expected_hash(self, sarif_path):
        path = sarif_path(
            {
                "runs": [
                    {
                        "results": [
                            {"ruleId": "R1", "level": "error", "message": {"text": "m"}}
                        ]
                    }
                ]
            }
        )
        normalize(path, "lbl")
        expected = hashlib.sha256("lbl|R1|error|m".encode()).hexdigest()
        data = json.loads(Path(path).read_text())
        assert (
            data["runs"][0]["results"][0]["partialFingerprints"]["stableResultHash"]
            == expected
        )

    def test_trivy_mode_uses_package_seed(self, sarif_path):
        msg = "Package: libfoo\nInstalled Version: 1.0\nFixed Version: 1.1\n"
        path = sarif_path(
            {
                "runs": [
                    {
                        "results": [
                            {
                                "ruleId": "CVE-0",
                                "level": "error",
                                "message": {"text": msg},
                            }
                        ]
                    }
                ]
            }
        )
        normalize(path, "cva", trivy=False)
        std_fp = json.loads(Path(path).read_text())["runs"][0]["results"][0][
            "partialFingerprints"
        ]["stableResultHash"]
        normalize(path, "cva", trivy=True)
        trivy_fp = json.loads(Path(path).read_text())["runs"][0]["results"][0][
            "partialFingerprints"
        ]["stableResultHash"]
        assert std_fp != trivy_fp

    def test_existing_partial_fingerprints_key_preserved(self, sarif_path):
        path = sarif_path(
            {
                "runs": [
                    {
                        "results": [
                            {
                                "ruleId": "R1",
                                "level": "note",
                                "message": {"text": "m"},
                                "partialFingerprints": {"otherKey": "val"},
                            }
                        ]
                    }
                ]
            }
        )
        normalize(path, "lbl")
        data = json.loads(Path(path).read_text())
        pf = data["runs"][0]["results"][0]["partialFingerprints"]
        assert "otherKey" in pf
        assert "stableResultHash" in pf

    def test_empty_results_produces_no_error(self, sarif_path):
        path = sarif_path({"runs": [{"results": []}]})
        normalize(path, "lbl")  # should not raise

    def test_multiple_results_all_fingerprinted(self, sarif_path):
        path = sarif_path(
            {
                "runs": [
                    {
                        "results": [
                            {
                                "ruleId": "R1",
                                "level": "error",
                                "message": {"text": "a"},
                            },
                            {
                                "ruleId": "R2",
                                "level": "warning",
                                "message": {"text": "b"},
                            },
                        ]
                    }
                ]
            }
        )
        normalize(path, "lbl")
        data = json.loads(Path(path).read_text())
        fps = [
            r["partialFingerprints"]["stableResultHash"]
            for r in data["runs"][0]["results"]
        ]
        assert fps[0] != fps[1]
        assert all(len(fp) == 64 for fp in fps)
