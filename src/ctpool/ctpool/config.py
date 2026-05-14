"""Application configuration loaded from environment variables via pydantic-settings.

All configuration values are validated at import time. Missing required fields
(e.g. DATABASE_URL) raise a ValidationError immediately on startup.
"""

from __future__ import annotations

import functools
import os

from pydantic import Field, PostgresDsn, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Validated application settings sourced from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Database — required; no default
    database_url: PostgresDsn
    database_admin_url: PostgresDsn | None = None

    # Ingestion behavior
    ct_backfill_days: int = 30
    """Days of CT log history to seed on first encounter.

    The backfill worker estimates a pivot index from the log's STH timestamp
    and ``first_seen_at``, then seeds only ranges covering the most recent
    ``ct_backfill_days`` days.  Set to ``0`` to seed the full log history
    from index 0 (may be billions of entries for large logs).
    """
    ct_tail_interval_seconds: int = 300
    ct_default_batch_size: int = 256
    ct_max_batch_size: int = 1024
    ct_deadlock_max_retries: int = 3
    ct_deadlock_base_backoff_seconds: float = 0.05
    ct_deadlock_max_backoff_seconds: float = 1.0
    ct_db_contention_enabled: bool = True
    ct_db_contention_ema_alpha: float = Field(default=0.25, gt=0.0, le=1.0)
    ct_db_contention_high_retry_ratio: float = Field(default=0.05, ge=0.0)
    ct_db_contention_low_retry_ratio: float = Field(default=0.01, ge=0.0)
    ct_db_contention_recovery_windows: int = Field(default=3, ge=1)
    ct_db_contention_sleep_step_seconds: float = Field(default=0.25, ge=0.0)
    ct_db_contention_max_sleep_seconds: float = Field(default=5.0, ge=0.0)
    ct_db_contention_jitter_fraction: float = Field(default=0.25, ge=0.0, le=1.0)
    ct_db_contention_min_batch_size: int = Field(default=16, ge=1)
    ct_db_contention_batch_growth_step: int = Field(default=32, ge=1)
    ct_db_contention_stale_after_seconds: int = Field(default=120, ge=1)
    ct_db_contention_enable_batch_cap: bool = True
    ct_rate_limit_backoff_seconds: int = 30
    ct_rate_limit_backoff_max_seconds: int = 300
    ct_retry_after_max_seconds: int = 3600
    """Maximum number of seconds to honour from a ``Retry-After`` header.

    If the server requests a longer delay it will be clamped to this value.
    """

    # Metrics retention
    ct_metrics_retention_days: int = 14
    """Days of ingestion_metrics rows to retain.  Older rows are pruned."""
    ct_metrics_prune_interval_seconds: int = 3600
    """Minimum seconds between automatic ingestion_metrics prune runs."""

    # Backfill claim durability
    ct_backfill_claim_timeout_seconds: int = 1800
    """Seconds after which an in_progress backfill range with no recent
    heartbeat is considered stale and eligible for reaping.
    """
    ct_backfill_heartbeat_seconds: int = 60
    """Interval in seconds at which active backfill workers refresh heartbeat_at."""

    # Worker runtime / ownership
    ct_worker_heartbeat_seconds: int = 15
    """Interval (s) at which workers refresh their ct_worker_runtime heartbeat."""
    ct_worker_stale_seconds: int = 300
    """Seconds without a heartbeat after which a worker claim is considered stale."""
    ct_worker_assignment_refresh_seconds: int = 30
    """Seconds between log assignment refresh checks in the worker loop."""

    # Worker pool concurrency
    ct_tail_concurrency: int = Field(
        default_factory=lambda: os.cpu_count() or 4,
        ge=0,
    )
    """Number of concurrent tail worker tasks launched by the pool.

    Defaults to ``os.cpu_count()`` (logical CPUs on the host), falling back
    to 4 when that cannot be determined.  CT log ingestion is I/O and network
    bound, so matching CPU count is a reasonable default.  Set to ``0`` to
    disable the tail pool entirely (useful when debugging or when tail is
    handled externally).  Override via ``CT_TAIL_CONCURRENCY=<n>``.
    """
    ct_backfill_concurrency: int = Field(
        default_factory=lambda: os.cpu_count() or 4,
        ge=0,
    )
    """Number of concurrent backfill worker tasks launched by the pool.

    Same default logic as ``ct_tail_concurrency``.  Once all CT logs have
    finished their initial backfill window the pool will find no eligible
    logs and idle efficiently.  Set to ``0`` to disable backfill entirely
    once historical ingestion is complete.  Override via
    ``CT_BACKFILL_CONCURRENCY=<n>``.
    """

    # Backfill dispatch model
    ct_backfill_dispatch_mode: str = "per-log"
    """Backfill dispatch model.

    ``per-log`` (default): one worker claims one CT log via
    ``ct_log_backfill_state`` and processes its window using a per-log
    durable checkpoint. The legacy ``ct_log_backfill_ranges`` table is
    not used by the normal runtime.

    ``legacy-ranges``: legacy compatibility mode. Workers claim individual
    ranges from ``ct_log_backfill_ranges`` and mark them complete or failed.
    Reserved for backfill-range repair, audit, and migration scenarios.
    """

    # Per-log retry budget (Sprint 3 — self-healing ingestion)
    ct_batch_retry_max_attempts: int = 10
    """Maximum consecutive retryable batch failures before pausing the log."""
    ct_batch_retry_max_seconds: int = 3600
    """Maximum age (seconds) of the first failure before pausing the log."""

    # Disk safety thresholds (GiB)
    ct_min_free_disk_gb: int = 50
    ct_critical_free_disk_gb: int = 20
    ct_disk_check_path: str = "/data/pgcheck"
    """Filesystem path used for free-disk checks.

    Must resolve to the volume where PostgreSQL data lives.  In the Docker
    Compose stack the postgres_data named volume is mounted read-only at this
    path inside each worker container.  Override when using an external DB or
    a non-standard mount point.
    """

    # HTTP behavior
    ct_http_timeout_seconds: int = 30
    ct_max_retries: int = 5
    ct_backoff_max_seconds: int = 300
    ct_operator_contact: str = ""
    """Optional contact string included in the HTTP User-Agent header.

    Set this to an email address, URL, or other identifier so that CT log
    operators can reach the specific deployment if they observe unusual
    traffic.  Example: ``admin@example.com`` or ``https://status.example.com``.
    When empty (the default), the machine hostname alone is used.
    """
    ct_fetch_degraded_resume_seconds: int = 3600
    """Seconds before a fetch-error-exhausted log is automatically retried.

    When the per-log retry budget is exhausted by transient fetch errors
    (HTTP 5xx, timeouts, connection errors) the log enters ``degraded``
    status and is held off for this many seconds before any worker picks
    it up again.  Defaults to 3600 (1 hour).  Only ``FATAL`` configuration
    or protocol errors keep the log permanently ``paused``.
    """

    # CT log list source — compile-time constant; not user-configurable at runtime
    # (SSRF prevention: CT log URLs originate from this trusted source only)
    ct_log_list_url: str = "https://www.gstatic.com/ct/log_list/v3/log_list.json"

    # Certificate retention
    ct_expired_cert_retention_days: int = 30
    """Days after a certificate's not_after before it is eligible for pruning.

    Only certificates that are not the latest cert for any hostname are pruned.
    Set to 0 to make all expired certs immediately eligible.
    """

    # Doctor health-check thresholds
    ct_doctor_tail_lag_warning_seconds: int = 3600
    """Tail-cursor lag above this threshold is a doctor warning."""
    ct_doctor_tail_lag_critical_seconds: int = 86400
    """Tail-cursor lag above this threshold is a doctor critical finding."""
    ct_doctor_disk_warning_pct: float = 80.0
    """Disk usage above this percentage triggers a doctor warning."""
    ct_doctor_disk_critical_pct: float = 90.0
    """Disk usage above this percentage triggers a doctor critical finding."""
    ct_doctor_http_error_warning: int = 1
    """HTTP error count above this triggers a doctor warning."""
    ct_doctor_http_error_critical: int = 100
    """HTTP error count above this triggers a doctor critical finding."""
    ct_doctor_metrics_stale_warning_seconds: int = 900
    """Age of most-recent ingestion_metrics row above this is a warning."""

    # Storage profiles (T9)
    ct_storage_profile: str = "lite"
    """Active storage profile.  One of: lite, standard, research, archive, custom."""
    ct_cert_storage_mode: str = "none"
    """Certificate storage mode.

    none             — hostnames + observations only; no durable cert rows.
    metadata         — cert metadata fields; no raw binary blobs.
    metadata_spki    — cert metadata; semantically equivalent to 'metadata' in
                       the current schema (spki_sha256 is always stored).
    metadata_public_key — metadata + public_key_der BYTEA (requires migration).
    full_der         — metadata + public_key_der + raw_der BYTEA.
    """
    ct_hostname_retention_mode: str = "forever"
    """Hostname retention policy.  'forever' keeps all hostnames indefinitely.
    'window' applies ct_cert_retention_days as a rolling window.
    """
    ct_cert_retention_days: int = 7
    """Days to retain certificate rows (when cert storage mode is not 'none')."""
    ct_observation_retention_days: int = 7
    """Days to retain ct_log_observations rows."""
    ct_entry_outcome_retention_days: int = 7
    """Days to retain ct_entry_outcomes rows."""
    ct_archive_explicit_optin: bool = False
    """Must be True to activate the 'archive' storage profile.

    The archive profile retains full DER and extended history; it is TB-scale
    storage.  Setting this to True is an explicit acknowledgement of that cost.
    """

    # Stats snapshot cadence
    ct_stats_live_refresh_seconds: int = 15
    """Interval in seconds for refreshing lightweight live stats (tail, rate)."""
    ct_stats_heavy_refresh_seconds: int = 30
    """Interval in seconds for refreshing heavy stats (projection, table sizes)."""
    ct_stats_snapshot_retention_hours: int = 24
    """Hours to retain old snapshot rows before pruning."""

    # Sprint 5: how old a stats snapshot may be before consumers should
    # treat it as stale.  Mirrors the API ``stats_stale_seconds`` setting
    # so the CLI ``ctpool status`` command and the API agree on what
    # "stale" means.  Must be greater than ``ct_stats_heavy_refresh_seconds``
    # (default 30 s); the default of 90 s tolerates two full missed cycles
    # with a 30 s margin before the warning fires.
    stats_stale_seconds: int = 90
    """Seconds beyond which a stats snapshot is considered stale."""

    # Maintenance service cadences
    ct_maintenance_interval_seconds: int = 3600
    """Seconds between maintenance loop cycles."""
    ct_audit_interval_seconds: int = 21600
    """Seconds between automatic audit-gap checks in the maintenance loop."""
    ct_prune_interval_seconds: int = 3600
    """Seconds between automatic prune runs in the maintenance loop."""

    # Scheduled audit opt-in (Sprint 4B). Deep audit-gap scans are expensive
    # and legacy-range-oriented; they are disabled by default in the normal
    # maintenance loop and must be explicitly enabled by the operator.
    bitsyscerts_enable_scheduled_audit: bool = False
    """If True, the maintenance loop runs check-audit-gaps on its interval."""
    bitsyscerts_audit_interval_seconds: int = 21600
    """Seconds between scheduled audit runs when explicitly enabled."""

    # Logging
    log_level: str = "INFO"

    @model_validator(mode="after")
    def validate_archive_guard(self) -> Settings:
        """Prevent accidental activation of the archive storage profile."""
        if self.ct_storage_profile == "archive" and not self.ct_archive_explicit_optin:
            raise ValueError(
                "ct_storage_profile='archive' requires "
                "ct_archive_explicit_optin=true. "
                "The archive profile is TB-scale storage. "
                "Set CT_ARCHIVE_EXPLICIT_OPTIN=true to confirm."
            )
        return self

    @model_validator(mode="after")
    def validate_db_contention_settings(self) -> Settings:
        """Validate cross-field relationships for DB contention controls."""
        if (
            self.ct_db_contention_low_retry_ratio
            > self.ct_db_contention_high_retry_ratio
        ):
            raise ValueError(
                "ct_db_contention_low_retry_ratio must be <= "
                "ct_db_contention_high_retry_ratio"
            )
        if (
            self.ct_db_contention_max_sleep_seconds
            < self.ct_db_contention_sleep_step_seconds
        ):
            raise ValueError(
                "ct_db_contention_max_sleep_seconds must be >= "
                "ct_db_contention_sleep_step_seconds"
            )
        if (
            self.ct_db_contention_enabled
            and self.ct_db_contention_min_batch_size > self.ct_default_batch_size
        ):
            raise ValueError(
                "ct_db_contention_min_batch_size must be <= ct_default_batch_size"
            )
        return self


@functools.lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the cached singleton Settings instance."""
    return Settings()  # type: ignore[call-arg]
