"""Tests for ctpool.normalizer — hostname normalization and NormalizedEntry building."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest

from ctpool.normalizer import (
    _resolve_tldextract_cache_dir,
    build_normalized_entry,
    extract_registrable_domain,
    normalize_hostnames,
)
from ctpool.pipeline_schemas import NormalizedEntry, ParsedCertificate

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _dummy_parsed(**kwargs: object) -> ParsedCertificate:
    """Return a minimal ParsedCertificate with overridable fields."""
    now = datetime(2024, 1, 1, tzinfo=UTC)
    defaults: dict[str, object] = {
        "fingerprint_sha256": "aabbcc",
        "spki_sha256": "ddeeff",
        "serial_number": "01",
        "issuer_dn": "CN=Test",
        "issuer_common_name": "Test",
        "issuer_organization": None,
        "subject_dn": "CN=Test",
        "subject_common_name": "Test",
        "not_before": now,
        "not_after": now,
        "signature_algorithm_oid": "1.2.840.10045.4.3.2",
        "signature_algorithm_name": "ecdsa-with-SHA256",
        "public_key_algorithm_oid": "1.2.840.10045.2.1",
        "public_key_algorithm_name": "EC",
        "public_key_bits_or_curve": "P-256",
        "is_precertificate": False,
        "san_dns_names": [],
    }
    defaults.update(kwargs)
    return ParsedCertificate(**defaults)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# normalize_hostnames
# ---------------------------------------------------------------------------


def test_normalize_hostnames_lowercases() -> None:
    """normalize_hostnames converts names to lowercase."""
    result = normalize_hostnames(["TEST.Example.COM"])
    assert result == ["test.example.com"]


def test_normalize_hostnames_strips_trailing_dot() -> None:
    """normalize_hostnames strips trailing dots from each name."""
    result = normalize_hostnames(["example.com."])
    assert result == ["example.com"]


def test_normalize_hostnames_removes_duplicates() -> None:
    """normalize_hostnames deduplicates values."""
    result = normalize_hostnames(["a.example.com", "a.example.com", "b.example.com"])
    assert result == ["a.example.com", "b.example.com"]


def test_normalize_hostnames_returns_sorted_output() -> None:
    """normalize_hostnames returns deterministic lexicographically sorted output."""
    result = normalize_hostnames(["z.example.com", "a.example.com"])
    assert result == ["a.example.com", "z.example.com"]


def test_normalize_hostnames_removes_empty_strings() -> None:
    """normalize_hostnames skips empty strings and names that become empty."""
    result = normalize_hostnames(["", ".", "  "])
    # "  ".lower().rstrip(".") == "  " which is truthy so it stays
    assert "" not in result
    assert "." not in result


def test_normalize_hostnames_empty_input_returns_empty() -> None:
    """normalize_hostnames returns an empty list for empty input."""
    assert normalize_hostnames([]) == []


def test_normalize_hostnames_preserves_wildcards() -> None:
    """normalize_hostnames keeps wildcard prefixes (*.example.com)."""
    result = normalize_hostnames(["*.Example.COM"])
    assert result == ["*.example.com"]


# ---------------------------------------------------------------------------
# extract_registrable_domain
# ---------------------------------------------------------------------------


def test_extract_registrable_domain_simple() -> None:
    """extract_registrable_domain returns 'example.com' for 'sub.example.com'."""
    assert extract_registrable_domain("sub.example.com") == "example.com"


def test_extract_registrable_domain_ccld() -> None:
    """extract_registrable_domain handles multi-part TLDs like .co.uk."""
    result = extract_registrable_domain("api.example.co.uk")
    assert result == "example.co.uk"


def test_extract_registrable_domain_wildcard() -> None:
    """extract_registrable_domain strips '*.'' before extraction."""
    assert extract_registrable_domain("*.example.com") == "example.com"


def test_extract_registrable_domain_bare_domain() -> None:
    """extract_registrable_domain returns the domain when no subdomain is present."""
    assert extract_registrable_domain("example.com") == "example.com"


def test_extract_registrable_domain_localhost_returns_clean_string() -> None:
    """extract_registrable_domain returns the input when extraction yields no domain."""
    # 'localhost' has no public suffix, so tldextract finds no domain+suffix
    result = extract_registrable_domain("localhost")
    assert isinstance(result, str)
    assert len(result) > 0


def test_resolve_tldextract_cache_dir_uses_env_override(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """CT_TLDEXTRACT_CACHE_DIR takes precedence and is created if missing."""
    override = tmp_path / "custom-cache"
    monkeypatch.setenv("CT_TLDEXTRACT_CACHE_DIR", str(override))
    cache_dir = _resolve_tldextract_cache_dir()
    assert cache_dir == str(override)
    assert override.is_dir()


# ---------------------------------------------------------------------------
# build_normalized_entry
# ---------------------------------------------------------------------------


def test_build_normalized_entry_returns_normalized_entry() -> None:
    """build_normalized_entry returns a NormalizedEntry."""
    parsed = _dummy_parsed(san_dns_names=["test.example.com"])
    log_id = uuid.uuid4()
    result = build_normalized_entry(parsed, log_id, log_index=42)
    assert isinstance(result, NormalizedEntry)


def test_build_normalized_entry_sets_log_source_id_and_index() -> None:
    """log_source_id and log_index are forwarded to NormalizedEntry."""
    parsed = _dummy_parsed()
    log_id = uuid.uuid4()
    result = build_normalized_entry(parsed, log_id, log_index=99)
    assert result.log_source_id == log_id
    assert result.log_index == 99


def test_build_normalized_entry_detects_wildcard() -> None:
    """is_wildcard_present is True when any SAN starts with '*.'."""
    parsed = _dummy_parsed(san_dns_names=["*.example.com", "example.com"])
    result = build_normalized_entry(parsed, uuid.uuid4(), log_index=0)
    assert result.is_wildcard_present is True


def test_build_normalized_entry_no_wildcard() -> None:
    """is_wildcard_present is False when no SAN starts with '*.'."""
    parsed = _dummy_parsed(san_dns_names=["app.example.com"])
    result = build_normalized_entry(parsed, uuid.uuid4(), log_index=0)
    assert result.is_wildcard_present is False


def test_build_normalized_entry_normalizes_hostnames() -> None:
    """Hostnames in NormalizedEntry are lowercased and deduped."""
    parsed = _dummy_parsed(san_dns_names=["UPPER.Example.COM", "upper.example.com."])
    result = build_normalized_entry(parsed, uuid.uuid4(), log_index=0)
    assert result.hostnames == ["upper.example.com"]
