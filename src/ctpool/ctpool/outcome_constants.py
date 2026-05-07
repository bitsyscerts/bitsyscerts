"""Terminal outcome labels for CT entry processing.

These constants define the allowed values for the ``outcome`` column in
``ct_entry_outcomes``.  Always use these constants instead of bare strings
so that typos are caught at import time.

Exports:
    OUTCOME_STORED               — Certificate and observation stored successfully.
    OUTCOME_PARSE_ERROR          — Entry could not be decoded or parsed.
    OUTCOME_UNSUPPORTED_ENTRY_TYPE — Entry type is valid per RFC 6962 but not
                                     handled by this parser version.
    OUTCOME_SKIPPED_BY_POLICY    — Entry skipped intentionally by operator policy.
    ALL_OUTCOMES                 — Frozenset of every allowed outcome string.
"""

from __future__ import annotations

OUTCOME_STORED: str = "stored"
OUTCOME_PARSE_ERROR: str = "parse_error"
OUTCOME_UNSUPPORTED_ENTRY_TYPE: str = "unsupported_entry_type"
OUTCOME_SKIPPED_BY_POLICY: str = "skipped_by_policy"

ALL_OUTCOMES: frozenset[str] = frozenset(
    [
        OUTCOME_STORED,
        OUTCOME_PARSE_ERROR,
        OUTCOME_UNSUPPORTED_ENTRY_TYPE,
        OUTCOME_SKIPPED_BY_POLICY,
    ]
)
