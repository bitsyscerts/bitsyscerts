"""ctpool — Certificate Transparency ingestion, indexing, and intelligence CLI.

Exports: Settings, CtPoolError hierarchy, core pipeline helpers, Tier 4/5/6 workers.
"""

from ctpool.backfill_worker import run_backfill
from ctpool.cert_writer import (
    upsert_certificate,
    upsert_certificate_hostname,
    upsert_hostname,
)
from ctpool.config import Settings, get_settings
from ctpool.dispatcher import (
    advance_tail_cursor,
    claim_backfill_range,
    create_backfill_ranges,
    ensure_tail_cursor,
    get_eligible_backfill_logs,
    get_eligible_tail_logs,
    mark_range_complete,
    mark_range_failed,
)
from ctpool.exceptions import (
    ConfigurationError,
    DatabaseError,
    DiskGuardError,
    DispatcherError,
    FetchError,
    ParseError,
    RateLimitError,
)
from ctpool.fetcher import fetch_entries, fetch_sth
from ctpool.http_client import build_httpx_client
from ctpool.log_discovery import fetch_log_list, sync_log_sources
from ctpool.log_prober import probe_log
from ctpool.metrics import LogMetricsAccumulator
from ctpool.normalizer import build_normalized_entry, normalize_hostnames
from ctpool.observation_writer import upsert_observation
from ctpool.parser import parse_leaf_entry
from ctpool.stats import render_stats, render_stats_watch
from ctpool.tail_worker import run_tail
from ctpool.writer import write_normalized_entry

__all__ = [
    "ConfigurationError",
    "DatabaseError",
    "DiskGuardError",
    "DispatcherError",
    "FetchError",
    "LogMetricsAccumulator",
    "ParseError",
    "RateLimitError",
    "Settings",
    "advance_tail_cursor",
    "build_httpx_client",
    "build_normalized_entry",
    "claim_backfill_range",
    "create_backfill_ranges",
    "ensure_tail_cursor",
    "fetch_entries",
    "fetch_log_list",
    "fetch_sth",
    "get_eligible_backfill_logs",
    "get_eligible_tail_logs",
    "get_settings",
    "mark_range_complete",
    "mark_range_failed",
    "normalize_hostnames",
    "parse_leaf_entry",
    "probe_log",
    "render_stats",
    "render_stats_watch",
    "run_backfill",
    "run_tail",
    "sync_log_sources",
    "upsert_certificate",
    "upsert_certificate_hostname",
    "upsert_hostname",
    "upsert_observation",
    "write_normalized_entry",
]
