---
description: "Use when creating or modifying any source file under src/ that defines database tables, ingestion pipelines, retention/pruning logic, storage projections, or API endpoints that expose retention settings. Encodes AGENTS.md retention guardrails as actionable rules."
applyTo: "src/**"
---

# Retention and Storage Guardrails

BitsysCerts is a **current, query-oriented** CT intelligence service — not a full historical
mirror of the public CT ecosystem. Every table, every ingestion loop, and every storage
estimate MUST be designed with bounded growth in mind. Violating any rule below is a defect.

---

## What BitsysCerts Is

Use this description in all documentation, comments, and user-facing copy:

> A self-hostable Certificate Transparency intelligence service for current hostname
> discovery, certificate metadata lookup, and OSINT pivot support.

MUST NOT describe BitsysCerts as a complete CT mirror, a full replacement for historical
`crt.sh` use cases, a complete archive of all public certificates, or a permanent copy of
all CT log data.

---

## Default Retention Mode: `current-osint`

All code MUST be written to honour the `current-osint` default. This is the mode that ships
out of the box. Any code that enables archive-mode behavior without explicit operator
configuration is a defect.

| Profile         | Default?  | Storage class        | Notes                                                       |
| --------------- | --------- | -------------------- | ----------------------------------------------------------- |
| `current-osint` | **Yes**   | GB-class             | Fresh OSINT and hostname discovery; bounded rolling windows |
| `research`      | No        | GB–TB-class          | Longer lookback; richer metadata; still not a full archive  |
| `archive`       | **Never** | TB-class or multi-TB | Must require explicit opt-in configuration                  |

The `archive` profile MUST never be activated by default.

---

## Mandatory Table Retention Policy

### Rule: No unbounded table from CT ingestion

Every table that grows from CT ingestion data MUST have **one** of the following:

1. **A time-bounded rolling-window prune** — rows older than a configurable window are
   deleted on a regular schedule.
2. **A foreign key cascade** — rows are automatically deleted when the parent entity is
   removed (e.g., observation deleted when log source is deactivated).
3. **A hard cardinality bound** — the table is inherently bounded by the number of unique
   entities (e.g., one row per CT log = ≤ 50 rows).

**A table with none of the above is a defect.** Before merging any migration that creates a
new table, confirm which category applies and document it in a migration comment.

### Audit trail tables

Tables that record maintenance history (e.g., `ct_maintenance_runs`, `ct_prune_runs`) MUST
be pruned to a configurable retention window (default: 90 days). They are not exempt from
retention requirements just because they are "internal."

---

## Prune Coverage Checklist

Before declaring a pruning feature complete, verify that ALL of the following tables
touched by CT ingestion are covered by at least one pruner:

| Table                                     | Expected Pruner                                                      |
| ----------------------------------------- | -------------------------------------------------------------------- |
| `ct_log_observations`                     | `prune-for-storage-profile` → observations category                  |
| `ct_entry_outcomes`                       | `prune-for-storage-profile` → outcomes category                      |
| `ingestion_metrics`                       | `prune-for-storage-profile` → metrics category                       |
| `certificates`                            | `prune-for-storage-profile` → certificates category (cert mode only) |
| `ingestion_errors`                        | `prune-for-storage-profile` → errors category                        |
| `ct_maintenance_runs`                     | `prune-for-storage-profile` → audit trail category                   |
| `ct_prune_runs`                           | `prune-for-storage-profile` → audit trail category                   |
| `ct_log_backfill_ranges` (completed rows) | `prune-for-storage-profile` → completed ranges                       |

A table absent from this list and absent from the pruner is an unbounded table — defect.

---

## DB-Backed Settings Must Be Honoured

When a pruner reads retention window configuration, it MUST read from the **database-backed
settings** (`CtInstanceSettings`) first, and fall back to environment variable defaults only
when no DB row exists.

MUST NOT read only from environment variables when a DB settings record is present. Operators
who change retention windows through the API MUST see those changes reflected in actual
pruning behavior without restarting the service.

```python
# WRONG — ignores DB-backed settings:
settings = get_settings()
window = settings.ct_observation_retention_days

# CORRECT — reads DB first, falls back to env:
db_settings = await get_active_instance_settings(session)
window = (
    db_settings.observation_retention_days
    if db_settings
    else get_settings().ct_observation_retention_days
)
```

---

## No Raw Data Retention by Default

- Full raw certificate DER blobs, full certificate chains, and raw CT log entry bytes MUST
  be optional and time-bounded. They MUST NOT be stored by default.
- The `cert_storage_mode` for the `current-osint` profile MUST default to `"none"`.
- Any code path that stores raw certificate data MUST be gated on
  `cert_storage_mode != "none"`.

---

## Deduplication Requirements

Ingestion code MUST deduplicate aggressively before writing:

- Use `(log_source_id, log_index)` as the unique key for CT log entries.
- Use `fingerprint_sha256` as the unique key for certificates.
- Use `hostname` as the unique key for hostname records.
- Use `(hostname, fingerprint_sha256)` as the unique key for certificate-hostname
  associations.

MUST NOT insert a row without first checking for an existing row on these keys. Use
`INSERT ... ON CONFLICT DO NOTHING` or `ON CONFLICT DO UPDATE` as appropriate.

---

## Configurable Retention Windows

All retention windows MUST be configurable. MUST NOT hardcode retention window values
anywhere except as defaults in settings configuration:

- DB-backed defaults belong in `profile_defaults.py` (or equivalent).
- Env-var defaults belong in `config.py` `Settings` class.
- Migration defaults belong in an `op.execute("INSERT INTO ct_instance_settings ...")`
  in the initial schema migration.

When adding a new prunable category, the retention window MUST be added to all three
locations.

---

## Storage Metrics Exposure

The application MUST expose row-count and storage metrics for all CT ingestion tables.
These metrics MUST be visible in the `/v1/stats/storage` endpoint (or equivalent).
MUST NOT add a new ingestion table without also adding it to the metrics query.

---

## Non-Goals — Do Not Implement Without an ADR

Do not implement the following without an explicit Architectural Decision Record:

- Mirroring every CT log forever.
- Retaining every certificate ever observed (beyond what `cert_storage_mode` controls).
- Retaining every duplicate CT log entry.
- Storing full public key material by default.
- Reconstructing the full historical certificate state of the internet.
- Becoming a general-purpose internet archive.
- Absorbing BitsysTools or BitsysTrace functionality.

If a requested feature would implement any of the above, stop and surface it explicitly to
the user before writing code.

---

## Integration Boundary

BitsysCerts provides CT intelligence. It does not absorb functionality from BitsysTools or
BitsysTrace. Any feature request that belongs in a consumer project MUST be rejected with an
explanation of why it falls outside BitsysCerts' scope.
