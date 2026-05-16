# BitsysCerts — Agent Handoff Document

> **How to use this file:** Read it at the start of every new agent session.
> The current status, next step, and verification commands tell you exactly where
> to pick up. Update "Completed Work" and "Next Step" as you finish each item.

---

## Current Status

**Active phase:** Phase 2 — see below for next steps  
**Phase 0 (Customization Files): COMPLETE** ✓  
**Phase 1A (Storage Root Cause): COMPLETE** ✓  
**Phase 1B (Hostname Search Fix): COMPLETE** ✓  
**Phase 1C (Dashboard False-Positives): COMPLETE** ✓

> **Next:** Phase 2 work items. Check HANDOFF.md Phase 2 section (if present) or define next priorities.

---

## Completed Work

| # | File | What Changed |
|---|------|--------------|
| 0 | `docs/HANDOFF.md` | Created this file — living cross-session state document |
| 1 | `.github/copilot-instructions.md` | Created workspace-level always-active Copilot baseline |
| 2 | `.github/instructions/database.instructions.md` | Created — Alembic rules, CT-scale index design, autovacuum, async session patterns |
| 3 | `.github/instructions/retention.instructions.md` | Created — encodes AGENTS.md retention guardrails as a live `applyTo: "src/**"` instruction |
| 4 | `.github/instructions/python.instructions.md` | Added `mypy` to the Definition of Done gate between ruff and pytest |
| 5 | `.github/prompts/new-python-module.prompt.md` | Added `src/ctpool/` sub-project path examples alongside `src/api/` examples |
| 7 | `src/ctpool/ctpool/profile_projection.py` | `_DAILY_CT_ENTRIES_ESTIMATE` 4M → 12M; `_INDEX_OVERHEAD_FACTOR` 1.35 → 2.2 |
| 8 | `src/ctpool/ctpool/profile_defaults.py` | LITE: `cert_storage_mode` none→metadata; `observation_retention_days` 7→1; `entry_outcome_retention_days` 7→1 |
| 9 | `src/ctpool/ctpool/storage_modes.py` | `_PROFILE_CERT_MODE[LITE]` NONE→METADATA for consistency |
| 10 | `src/ctpool/ctpool/_cli_prune_storage_profile_impl.py` | Added `_read_prune_params` (DB-backed settings with env fallback); refactored `_process_category` to dispatch table; added count/delete for `ingestion_errors`, `ct_maintenance_runs`, `ct_prune_runs`, `ct_log_backfill_ranges` (completed) |
| 11 | `src/ctpool/ctpool/prune_profile_plan.py` | Added 4 new `PruneCategory` entries; updated execute-mode console output to loop over categories |
| 12 | `src/ctpool/migrations/versions/a1b2c3d4e5f6_autovacuum_high_churn_tables.py` | New migration: tighter autovacuum for `ct_log_observations` + `ct_entry_outcomes` |
| 13 | `src/ctpool/tests/test_prune_storage_profile.py` | Added tests for DB-backed settings, new categories, fixed retention windows |
| 14 | `src/ctpool/tests/test_prune_profile_plan.py` | Updated to expect 8 categories |
| 15 | `src/ctpool/tests/test_profile_defaults.py` | Updated LITE assertions for new values |
| 16 | `src/ctpool/tests/test_storage_modes.py` | Updated `test_resolve_lite_profile_default` to expect METADATA |
| 17 | `src/ctpool/migrations/versions/b2c3d4e5f6a7_hostname_sort_indexes.py` | 1B-1: CONCURRENTLY sort indexes on `hostnames (latest_cert_not_before DESC, id DESC)` and `(latest_cert_not_after DESC, id DESC)` |
| 18 | `src/api/certsapi/database.py` | 1B-2: `statement_timeout=30000` added to `connect_args` in `create_async_engine` |
| 19 | `src/app/src/services/apiClient.ts` | 1B-3: `ApiTimeoutError` class, `_withTimeout` helper, 15 s `AbortController` on `apiFetch` |
| 20 | `src/app/src/hooks/usePaginatedSearch.ts` | 1B-4: `error: Error \| null` field added to `PaginatedSearchResult` interface |
| 21 | `src/app/src/pages/SearchPage/SearchPageContent.tsx` | 1B-4: Timeout/error alert UI — orange for `ApiTimeoutError`, red for other errors |
| 22 | `src/api/certsapi/config.py` | 1C-1: `stats_stale_seconds` default 90 → 360 (refresh cadence is 300 s) |
| 23 | `src/app/src/utils/deriveSystemStatus.ts` | 1C-2: `never_ran` maintenance status no longer surfaces as a warning |
| 24 | `src/ctpool/ctpool/prune_profile_plan.py` | Fixed: added `preserved_hostnames: int \| None = None` field to `PruneAggregate` (mypy error introduced by Phase 1A) |
| 25 | `.github/workflows/ci.yml` | CI/CD redesigned: fan-out/fan-in pattern with `gate` job; Semgrep promoted to hard gate; all publish jobs now share a single dependency so deployments are atomic |

---

## Remaining Phase 0 Steps

- [x] **Step 7 — Semgrep + CI/CD redesign:** COMPLETE. `continue-on-error` removed. CI
  restructured as fan-out / fan-in with a single `gate` job. All publish jobs (`build-push-api`,
  `build-push-app`, `package-runtime-bundles`) now share `needs: [version, gate]` — atomic
  versioned deployments enforced.

---

## Phase 1B — Hostname Search Fix

### Step 1B-1 · Missing sort indexes
New Alembic migration (**separate file from 1A-4** — CONCURRENTLY cannot run inside a transaction):  
```sql
CREATE INDEX CONCURRENTLY ix_hostnames_latest_cert_not_before
  ON hostnames (latest_cert_not_before DESC, id DESC);
CREATE INDEX CONCURRENTLY ix_hostnames_latest_cert_not_after
  ON hostnames (latest_cert_not_after DESC, id DESC);
```

### Step 1B-2 · Statement timeout on DB engine
**File:** `src/api/certsapi/database.py`  
Add `connect_args={"options": "-c statement_timeout=30000"}` to `create_async_engine(...)`.  
Use **30 s** at the engine level (not 15 s) — gives headroom for complex queries.
The frontend's 15 s `AbortController` fires first for users; 30 s prevents truly infinite hangs.

### Step 1B-3 · Fetch timeout in API client
**File:** `src/app/src/services/apiClient.ts`  
Add `AbortController` with 15 s timeout signal to `apiFetch()`.  
Return a structured error distinguishing `"query_timeout"` from other errors.

### Step 1B-4 · Surface timeout error in search UI
**File:** Hostname search results component (find via `src/app/src/hooks/useHostnameSearch.ts`)  
Detect timeout error → show `"Search timed out — try a more specific query"` instead of spinner.

---

## Phase 1C — Dashboard False-Positive Warnings (parallel with 1A and 1B)

### Step 1C-1 · Fix stats stale threshold
**File:** `src/api/certsapi/config.py`  
`stats_stale_seconds` default: `90` → `360`  
Rationale: snapshot refresh cadence is 300 s; 90 s threshold means stale 70% of the time normally.

### Step 1C-2 · Demote never-ran maintenance to info
**File:** `src/app/src/utils/deriveSystemStatus.ts`  
In `collectMaintenanceIssues`: change `maintenance.status === "never_ran"` severity from
`"warning"` → `"info"`. It is expected on first boot and is not an operator emergency.

---

## Key Technical Decisions

| Decision | Rationale |
|---|---|
| `hostname_retention_mode: "forever"` stays for LITE | Hostnames are the core product value |
| LITE projected storage is ~45 GB, not 17 GB | CT issuance is 12M/day; old estimate was 4M/day. Index overhead is 2.2×, not 1.35× |
| **LITE `cert_storage_mode`: `"none"` → `"metadata"`** | `"none"` sets `skip_cert=True` → skips ALL cert rows. Cert metadata IS product data. SANs are additional hostnames. Certificates page must work in LITE mode. |
| **LITE observation/outcome retention: 7 days → 1 day** | Processing receipts only — no dedup/audit value once fully processed. Reclaims ~20 GB. 24-hour audit gap window is acceptable for OSINT use case. |
| **`skip_cert` bug root cause** | Workers (`tail_worker.py`, `backfill_worker.py`, `backfill_per_log.py`) read `settings.ct_cert_storage_mode` from env vars via `Settings`, NOT from DB-backed `CtInstanceSettings`. If production's `.env` set `CT_CERT_STORAGE_MODE=metadata` (or any non-`none` value), certs were written despite the LITE DB profile saying `"none"`. The profile change to `"metadata"` makes this moot going forward. The systemic fix (workers reading DB-backed settings) is out of Phase 1A scope. |
| Pruner was ignoring DB-backed settings | `get_settings()` reads only env vars; `CtInstanceSettings` (set via UI) was never read |
| `ingestion_errors`, `ct_maintenance_runs`, `ct_prune_runs`, completed `ct_log_backfill_ranges` | No time-based pruner exists for any of these — they grow forever. Wire into `prune-for-storage-profile` orchestrator. |
| Stats stale threshold was 90 s vs 300 s refresh cadence | 70% false-positive warning rate by design |
| Semgrep is non-blocking in CI | Comment says to remove after initial triage — requires user decision |
| Hostname sort index was missing | Caused unbounded query duration on `ORDER BY latest_cert_not_before` with 26M rows |
| Statement timeout: 30 s engine-level, 15 s frontend abort | 30 s prevents infinite hangs server-side; 15 s `AbortController` fires first for users |

---

## Verification Commands (run after Phase 1 is complete)

```bash
# Storage projection is honest (should show ~40-50 GB, not 17 GB)
ctpool storage-profile

# Pruner dry-run includes all new tables
ctpool prune-for-storage-profile --dry-run

# Python linting and type checking (ctpool)
cd /workspaces/bitsyscerts/src/ctpool
ruff check ctpool/ tests/ && ruff format --check ctpool/ tests/ && mypy ctpool/

# Python linting and type checking (api)
cd /workspaces/bitsyscerts/src/api
ruff check certsapi/ tests/ && ruff format --check certsapi/ tests/ && mypy certsapi/

# Python tests
cd /workspaces/bitsyscerts/src/ctpool && pytest
cd /workspaces/bitsyscerts/src/api && pytest

# Frontend full check (lint + typecheck + vitest + coverage)
cd /workspaces/bitsyscerts/src/app && npm run test
```

---

## Repository Context

- **Repo:** `bitsyscerts/bitsyscerts` · branch: `staging`
- **Sub-projects:** `src/api/` (FastAPI), `src/app/` (React + Mantine), `src/ctpool/` (Python CLI)
- **Virtualenv:** `/workspaces/bitsyscerts/.venv` — activate before running Python tools
- **Database:** PostgreSQL 17, connection from `.env` (`DATABASE_URL`)
- **Deployment:** `docker compose up -d` from `src/` — see `src/docker-compose.yml`
