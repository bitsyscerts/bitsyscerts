# BitsysCerts Operations Guide

## Maintenance smoke path

After deploying or upgrading `ctpool`, run the following sequence to
validate that the lightweight maintenance loop is wired up correctly.
Each command is non-destructive in the order shown (the dry-run prune
inspects state but deletes nothing; the single-shot maintenance run uses
the configured retention windows).

```bash
ctpool prune-for-storage-profile --dry-run
ctpool maintenance --once
ctpool stats-snapshot --once
ctpool stats
```

What each step proves:

1. **`prune-for-storage-profile --dry-run`** — confirms the orchestrator
   can read settings, classify retention categories, and report
   candidate counts without deleting anything.
2. **`maintenance --once`** — runs one full lightweight maintenance
   cycle: profile-aware prune only, no deep audit-gap scan unless
   `BITSYSCERTS_ENABLE_SCHEDULED_AUDIT=true` is set and the audit
   interval has elapsed.
3. **`stats-snapshot --once`** — refreshes the cached storage and
   ingestion metrics row that the API serves.
4. **`stats`** — prints the latest snapshot so the operator can confirm
   row counts moved as expected.

## Current backfill runtime

Use the default `ctpool backfill` command for normal ingestion. BitsysCerts
runs **per-log dispatch** by default, and `ctpool backfill-state` is the
primary operator view for active backfill progress.

```bash
ctpool backfill
ctpool backfill-state
```

The following commands are retained only for advanced/debug legacy-range
compatibility workflows:

```bash
ctpool legacy-ranges status
ctpool reap-stale-backfill-claims
ctpool check-audit-gaps
ctpool fix-audit-findings --dry-run
```

## API Exposure

`/v1/stats` is enabled by default for normal self-hosted Docker Compose,
workstation, and lab VM deployments because it powers the bundled dashboard.
Set `BITSYSCERTS_EXPOSE_STATS_API=false` only for unusual deployments that need
to suppress operator stats behind a gateway or other access-control layer.

Do not expose operational endpoints such as `/v1/stats`, worker state,
maintenance status, settings, or legacy diagnostics directly to the public
internet. For public or demo deployments, place BitsysCerts behind an API
gateway such as Kong or Cloudflare Access and expose only intentionally public
read-only endpoints.

## Scheduled audit (opt-in)

The deep `check-audit-gaps` scan is **off by default**.  Enable it only
on operators that have spare I/O budget for a periodic full audit:

```bash
export BITSYSCERTS_ENABLE_SCHEDULED_AUDIT=true
export BITSYSCERTS_AUDIT_INTERVAL_SECONDS=21600   # 6 hours (default)
```

Audit failures are logged but never block the prune step.

## Concurrent prune protection

`prune-for-storage-profile` acquires a Postgres advisory lock for the
duration of its run.  A second invocation that arrives while the first
is still running will exit immediately with a clear error rather than
double-deleting rows.  The lock is released automatically when the
first run finishes (success or failure).

## Dashboard Metric Semantics

The dashboard uses precise, distinct labels for ingestion metrics so
operators can immediately tell observed throughput from new uniqueness.
The terms below are the canonical definitions:

- **Observations processed** — CT log entries processed or durably
  accounted for.
- **Certificates parsed** — certificate payloads parsed from CT
  entries.
- **New unique certificates** — certificate fingerprints first seen by
  this instance.
- **Duplicate certificates** — certificate fingerprints already known.
- **Hostnames observed** — hostname appearances extracted from
  certificates. BitsysCerts counts normalized unique hostnames per
  certificate once (lowercased, trailing dot stripped, duplicates within
  the same certificate collapsed).
- **New unique hostnames** — hostname rows first inserted by this
  instance.
- **Known hostnames** — observed hostnames already known.

> High *observed-hostname* throughput with low *new-hostname* throughput
> usually means the instance is processing overlapping CT log data and
> deduplicating it successfully.  This is healthy.

High duplicate rates are expected when processing multiple CT logs because
the same certificate may appear in more than one log. Duplicate throughput
does not mean the system is broken; it means the indexer is deduplicating
overlapping CT observations.

### Snapshot freshness

The dashboard renders an "Updated Xs ago" badge near the top of the
stats panel.  The API marks a snapshot as **stale** when its age
exceeds `BITSYSCERTS_STATS_STALE_SECONDS` (default `120`).  Stale
snapshots are clearly indicated in both the UI and `ctpool status`;
they are never silently displayed as current numbers.

### `ctpool status`

A concise operator summary that reads the most recent stats snapshot.
It does **not** run heavy live queries — this command stays fast and
safe to run on busy hosts.

```bash
ctpool status
```

Sample output:

```text
BitsysCerts Status

Stats snapshot: fresh, generated 8s ago
Storage profile: lite, enforced
Workers: 12 active, 0 stale
Backfill: 8 processing, 1 retrying, 0 paused, 14 complete
Tail: 0 stale logs, oldest lag 6s
Ingestion:
  observations/min:      10,000
  certs parsed/min:      9,500
  new certs/min:         1,200
  duplicate certs/min:   8,300
  hostnames observed/min:22,000
  new hostnames/min:     180
  known hostnames/min:   21,820
Errors:
  retryable/min:         2
  terminal entries/min:  0
Maintenance: last prune complete 12m ago
```
