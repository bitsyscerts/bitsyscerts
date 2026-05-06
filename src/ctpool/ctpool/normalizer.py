"""Hostname normalization and NormalizedEntry construction.

Exports:
    normalize_hostnames      — Deduplicate and normalize a list of DNS SAN strings.
    extract_registrable_domain — Return the registrable domain for a hostname.
    build_normalized_entry   — Build a NormalizedEntry from a ParsedCertificate.
"""

from __future__ import annotations

import os
import tempfile
import uuid
from pathlib import Path

import tldextract

from ctpool.pipeline_schemas import NormalizedEntry, ParsedCertificate


def _resolve_tldextract_cache_dir() -> str | None:
    """Return a writable cache directory for tldextract, or None.

    Search order:
    1. ``CT_TLDEXTRACT_CACHE_DIR`` (explicit override)
    2. ``$XDG_CACHE_HOME/ctpool/tldextract``
    3. ``$TMPDIR/ctpool-tldextract-cache``

    Returns ``None`` when no candidate can be created/written, which tells
    tldextract to run without a filesystem cache (silences permission warnings).
    """
    candidates: list[Path] = []

    override = os.environ.get("CT_TLDEXTRACT_CACHE_DIR")
    if override:
        candidates.append(Path(override).expanduser())

    xdg_cache_home = os.environ.get("XDG_CACHE_HOME")
    if xdg_cache_home:
        candidates.append(Path(xdg_cache_home).expanduser() / "ctpool" / "tldextract")

    candidates.append(Path(tempfile.gettempdir()) / "ctpool-tldextract-cache")

    for candidate in candidates:
        try:
            candidate.mkdir(parents=True, exist_ok=True)
            return str(candidate)
        except OSError:
            continue

    return None


_tld = tldextract.TLDExtract(cache_dir=_resolve_tldextract_cache_dir())


def normalize_hostnames(san_dns_names: list[str]) -> list[str]:
    """Normalize and deduplicate SAN DNS names.

    Normalization rules:
    - Lowercase all characters.
    - Strip trailing dots.
    - Remove empty strings.
    - Deduplicate values.
    - Return lexicographically sorted output for deterministic write order.

    Args:
        san_dns_names: Raw DNS SAN values from a certificate.

    Returns:
        Sorted, deduplicated list of normalized hostnames.
    """
    seen: set[str] = set()
    result: list[str] = []
    for raw in san_dns_names:
        normalized = raw.lower().rstrip(".")
        if normalized and normalized not in seen:
            seen.add(normalized)
            result.append(normalized)
    return sorted(result)


def extract_registrable_domain(hostname: str) -> str:
    """Return the registrable domain portion of *hostname*.

    Uses ``tldextract`` so that both ``example.com`` and ``api.example.co.uk``
    return ``example.com`` / ``example.co.uk`` respectively.  Wildcards
    (``*.example.com``) have the leading ``*.`` stripped before extraction.

    Args:
        hostname: A normalized hostname string (lowercase, no trailing dot).

    Returns:
        The registrable domain (e.g. ``"example.com"``), or the full hostname
        if extraction fails.
    """
    clean = hostname.lstrip("*").lstrip(".")
    extracted = _tld(clean)
    if extracted.domain and extracted.suffix:
        return f"{extracted.domain}.{extracted.suffix}"
    return clean


def build_normalized_entry(
    parsed: ParsedCertificate,
    log_source_id: uuid.UUID,
    log_index: int,
) -> NormalizedEntry:
    """Construct a :class:`NormalizedEntry` from a parsed certificate.

    Args:
        parsed:        Populated :class:`ParsedCertificate`.
        log_source_id: UUID of the CT log this entry was fetched from.
        log_index:     Index of this entry in the CT log.

    Returns:
        :class:`NormalizedEntry` with normalized hostnames and wildcard flag.
    """
    hostnames = normalize_hostnames(parsed.san_dns_names)
    is_wildcard = any(h.startswith("*.") for h in hostnames)
    return NormalizedEntry(
        parsed_certificate=parsed,
        hostnames=hostnames,
        is_wildcard_present=is_wildcard,
        log_source_id=log_source_id,
        log_index=log_index,
    )
