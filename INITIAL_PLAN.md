# BitsysCerts — Initial Implementation Plan

> **Handoff document.** This file captures the full architectural plan, decomposition, build
> order, test plan, and implementation rules for the `ctpool` ingestion package. It is intended
> to be given verbatim to a coding LLM in a fresh Dev Container context so that implementation
> can begin without needing the original planning conversation.
>
> **Do not skip any section.** Every rule here reflects a project mandate that is enforced by
> linting, tests, and code review.

---

## Table of Contents

1. [Project Summary](#1-project-summary)
2. [Repository Rules — Non-Negotiable](#2-repository-rules--non-negotiable)
3. [Coding Standards Reference](#3-coding-standards-reference)
4. [Security Mandates](#4-security-mandates)
5. [Testing Mandates](#5-testing-mandates)
6. [Resolved Design Decisions](#6-resolved-design-decisions)
7. [Technology Stack](#7-technology-stack)
8. [Dev Container Specification](#8-dev-container-specification)
9. [Database Schema](#9-database-schema)
10. [Complete Unit Decomposition](#10-complete-unit-decomposition)
11. [Dependency Graph](#11-dependency-graph)
12. [Bottom-Up Build Order](#12-bottom-up-build-order)
13. [Infrastructure Files Specification](#13-infrastructure-files-specification)
14. [Complete Test Plan](#14-complete-test-plan)
15. [CLI Specification](#15-cli-specification)
16. [Configuration Reference](#16-configuration-reference)
17. [Operational Behavior Reference](#17-operational-behavior-reference)
18. [Implementation Checklist](#18-implementation-checklist)

---

## 1. Project Summary

**BitsysCerts** is a self-hostable Certificate Transparency (CT) intelligence service for
current hostname discovery, certificate metadata lookup, and OSINT pivot support.

It is **not** a full historical mirror of the public CT ecosystem. Its default operating
model is to retain the latest useful CT signal — not every historical raw certificate,
duplicate log entry, or full certificate chain forever. The project must avoid scope creep
toward becoming a second copy of the internet.

The ingestion package is named **`ctpool`** and is installed as a CLI tool (`ctpool`). The
immediate goal is a working ingestion system that runs from a VS Code Dev Container CLI,
accumulates CT log data into PostgreSQL, and resumes safely after interruption.

### What CT data is (and is not)

- **CT observation**: A certificate or precertificate containing a hostname was observed in a
  public CT log. This is all that ingestion records.
- **Not** authoritative DNS. **Not** proof of current hostname liveness.
- **Not** live TLS posture. DNS and TLS enrichment are future work, separate from CT ingestion.

### Product purpose — practical questions BitsysCerts answers

- **Hostname discovery:** What hostnames and subdomains have recently appeared for a domain?
- **Current exposure:** What names appear to be active or recently issued?
- **Certificate metadata:** What issuer, validity period, SAN relationships, and fingerprints
  are associated with observed names?
- **Pivot support:** What hostnames, registered domains, fingerprints, and SAN relationships
  can be used by BitsysTools and BitsysTrace?
- **Fresh signal:** What new CT observations have appeared recently?

BitsysCerts does not aim to preserve the full certificate history of every hostname on the
internet.

### Scope and default retention mode

The default retention mode is **`current-osint`**, optimised for current OSINT,
reconnaissance, and hostname discovery.

**Data kept long-term (durable hostname state):**

```
fqdn                     registered_domain      first_seen_at
last_seen_at             most_recent_not_before most_recent_not_after
latest_cert_fingerprint  latest_issuer          latest_source_log
observation_count        status_hint            created_at / updated_at
```

**Data retained for a bounded rolling window (defaults):**

| Data class | Default window |
|---|---|
| Recent certificate observations | 12 months |
| Hostname-certificate relationships | 12 months |
| SAN co-occurrence relationships | 12 months |
| Raw CT entry metadata | 30 – 180 days |
| Parsed raw certificate payload | 30 – 180 days (optional) |
| Duplicate log sightings | 30 – 180 days |

**Not retained by default:**

- Full raw certificate DER or certificate chains.
- Public key material.
- Every historical certificate instance for every hostname.
- Unbounded per-log raw response payloads.

Support for any of the above must be gated behind an explicit non-default retention profile.

### Retention profiles

| Profile | Purpose | Default? |
|---|---|---|
| `current-osint` | Fresh hostname discovery, current certificate metadata, OSINT pivots, bounded storage | **Yes** |
| `research` | Longer lookback, richer metadata retention, deeper relationship analysis | No |
| `archive` | Full CT archival. TB-class or multi-TB storage. Must never be the default | No |

### Integration boundaries

```
BitsysCerts  →  CT ingestion, normalisation, indexing, querying, reference UI
BitsysTools  →  consumes BitsysCerts CT intelligence for public diagnostics
BitsysTrace  →  consumes BitsysCerts CT intelligence for pivot workflows
```

BitsysCerts does not absorb BitsysTools or BitsysTrace functionality.

### Non-goals

- Mirroring every CT log forever.
- Retaining every certificate ever observed.
- Retaining every duplicate CT log entry.
- Reconstructing the full historical certificate state of the internet.
- Storing full public key material by default.
- Becoming a general-purpose internet archive.
- Replacing every historical feature of `crt.sh`.

### Primary use cases enabled by ingestion

- Hostname discovery for domains where zone transfer is unavailable.
- Certificate fingerprint pivoting.
- SPKI fingerprint correlation.
- Issuer pattern analysis.
- SAN co-occurrence and wildcard visibility.
- Integration with BitsysTrace OSINT pivot workflows.
- Enrichment for BitsysTools domain and host inspection.

### Immediate build priority (ordered)

1. Dev Container with in-container PostgreSQL.
2. Alembic migrations for the initial schema.
3. CT log discovery and metadata sync.
4. One-log tail worker with `--once` and `--limit`.
5. Certificate/precertificate parser.
6. Compact normalized database inserts.
7. CLI stats.
8. Multi-log tail.
9. Backfill range creation and claiming.
10. Backfill worker.
11. Rate-limit, backoff, and disk-safety behavior.
12. Log-follow and operational visibility.

---

## 2. Repository Rules — Non-Negotiable

The repository root is reserved exclusively for repository metadata. The following are the
**only** files permitted at the repo root:

```
README.md
AGENTS.md
INITIAL_PLAN.md   ← this file (planning document only)
.github/
.gitignore
LICENSE
.editorconfig
```

**Every source file, configuration file, and dependency manifest lives under `src/`.**

The monorepo structure:
```
src/
  ctpool/     ← Python CLI ingestion package (this plan)
  api/        ← future FastAPI service
  app/        ← future React/Vite frontend
```

`.devcontainer/` is permitted at the repo root because VS Code's Dev Container specification
requires it there. It is infrastructure metadata, not source code.

### File size limits (enforced, not aspirational)

| Lines     | Status  | Action required |
|-----------|---------|-----------------|
| ≤ 200     | Good    | None |
| 201–500   | Warning | Add a comment block at top of file explaining consolidation rationale |
| > 500     | Defect  | Split the file immediately. No other work proceeds until split is complete |

### Function/method size limits

| Lines | Status  | Action required |
|-------|---------|-----------------|
| ≤ 20  | Good    | None |
| 21–50 | Warning | Add inline comment explaining why extraction is not yet possible |
| > 50  | Defect  | Split the function before proceeding with any other work |

### Single Responsibility Principle

Every function, class, and module has exactly **one** responsibility. If the word "and" appears
when describing its purpose, it has too many.

### Bottom-up build order

Build leaves first. Compound objects are assembled from proven, tested components. Writing
top-down (page before component, service before utility) is prohibited. Tests must pass at each
tier before the next tier begins.

---

## 3. Coding Standards Reference

All Python code must comply with every rule below. These rules are enforced by `ruff` and
`mypy` as part of the unified test command.

### Style and formatting

- Full PEP-8 compliance.
- `ruff` is the enforced linter and formatter. Every file must pass `ruff check` and
  `ruff format` with zero warnings.
- Maximum line length: **88 characters**.
- Import order: standard library → third-party → local. No mixed groups.
- No wildcard imports (`from module import *`).

### Type hints

- All functions and methods must have complete type annotations on every parameter and return
  value. No unannotated signatures.
- Do not use `Any` from `typing` unless interacting with a third-party library that cannot be
  typed. Every `Any` must have an inline comment explaining why.
- Use `TypeAlias`, `TypeVar`, and `Protocol` for reusable type patterns.
- Pydantic `BaseModel` subclasses must be used for all structured data passed across module
  boundaries. Do not pass raw `dict` objects between layers.

### Package and module structure

- `__init__.py` files contain only re-exports of the module's public API. No implementation
  code, business logic, or class definitions.
- No catch-all module names. Prohibited: `utils.py`, `helpers.py`, `misc.py`, `common.py`,
  `shared.py`. Use domain-scoped names instead.

### Async

- All I/O operations must be `async`. Do not call synchronous blocking I/O from inside an
  async function.
- Use SQLAlchemy with the `asyncio` extension for all database access.
- Do not use `time.sleep()` in async context. Use `asyncio.sleep()`.
- Do not call `asyncio.run()` from within an already-async context.
- Concurrent tasks use `asyncio.gather()` or `asyncio.TaskGroup` with proper exception handling.

### Error handling

- Do not use bare `except:` or `except Exception:` without either re-raising or logging the
  full exception with context.
- Define domain-specific exception classes in `exceptions.py`. Do not raise generic
  `ValueError`, `RuntimeError`, or `Exception` from business logic.
- Exception messages must be safe for logging (no passwords, tokens, or PII).

### Docstrings

- All public functions, classes, and modules must have a one-line docstring.
- Functions with non-obvious behavior must have a full Google-style docstring with `Args:`,
  `Returns:`, and `Raises:` sections.
- `__init__.py` files must have a module-level docstring listing exports and domain coverage.

### Configuration

- Do not hardcode configuration values. Use Pydantic `BaseSettings` for all application
  configuration loaded from environment variables.

### Database

- Use SQLAlchemy async ORM with `psycopg` (psycopg3) as the driver.
- ORM models (SQLAlchemy) and pipeline models (Pydantic) must be separate classes.
- Migrations managed with Alembic. Never modify the schema manually.
- All database access uses parameterized queries or the ORM. Never construct SQL by string
  concatenation with user input.

---

## 4. Security Mandates

The following apply to every file under `src/`. They map to OWASP Top 10 (2021) and OWASP API
Top 10 (2023).

### Input validation (A03, API10)

- Validate and sanitize **all** data received from external CT log HTTP API responses before
  use. Do not assume third-party API responses conform to their documented schema.
- Use Pydantic models as the validation layer for all external data (CT log list JSON, CT entry
  responses, STH responses).
- Use allowlist validation for string patterns where feasible.

### Secrets management (A02)

- Never hardcode credentials, tokens, or database URLs. All secrets come from environment
  variables via `pydantic-settings`.
- The `DATABASE_URL` includes credentials. Do not log it or include it in exception messages.

### SQL injection (A03)

- All database writes use SQLAlchemy ORM `INSERT ... ON CONFLICT DO UPDATE` (upsert) patterns
  or Core constructs. Never construct SQL strings.

### SSRF prevention (A10, API7)

- CT log URLs come from the database only. They were originally sourced from the official
  Chrome CT log list JSON. Do not allow runtime user input to directly control outbound HTTP
  request targets.
- The log list source URL is a compile-time constant in `log_discovery.py`, not a
  user-supplied value.

### Logging (A09)

- Log authentication events, errors, retry events, and rate-limit events with sufficient
  context (timestamp, log ID, action, outcome).
- Never log: passwords, database credentials, full stack traces to stdout in production,
  internal connection strings.
- Exception messages must be sanitized before logging.

### Dependency pinning (A06)

- All dependencies in `pyproject.toml` must be pinned to specific versions (e.g.,
  `httpx==0.27.0`), not open ranges.
- Review CVE history before adding any new dependency.

### Data integrity (A08)

- Validate the structure of the CT log list JSON response before processing. Use Pydantic
  models with strict field requirements.
- Validate each CT log entry's structure before parsing the certificate data.

---

## 5. Testing Mandates

### Coverage gate (hard, not aspirational)

**75% on all four dimensions: statements, branches, functions, lines.**

CI fails below this threshold. Features do not ship below this threshold.

### Test-with-code rule

Test files are created in the same implementation step as the implementation they test. Tests
are never written in a follow-up step.

### Unified test command

From `src/ctpool/`:
```bash
pytest
```

**Important:** `pytest` alone does not run `ruff` or `mypy`. The "unified" command is
achieved by adding the following to dev dependencies and pytest config:

```toml
# Add to [project.optional-dependencies] dev in pyproject.toml:
"pytest-ruff==0.4.1",   # runs ruff as a pytest plugin — fails the suite on lint errors
"pytest-mypy==0.10.3",  # runs mypy as a pytest plugin — fails the suite on type errors
```

```toml
# Add to [tool.pytest.ini_options] in pyproject.toml:
addopts = "--ruff --mypy --cov=ctpool --cov-report=term-missing --cov-fail-under=75"
```

With this configuration, a single `pytest` invocation from `src/ctpool/` runs in sequence:
1. `ruff` lint check on all collected files (fails fast on lint errors)
2. `mypy` type check on all collected files
3. pytest test execution with asyncio support
4. Coverage report with `--cov-fail-under=75` on all dimensions

Alternatively, a `Makefile` at `src/ctpool/Makefile` with a `test` target is acceptable:
```makefile
test:
	ruff check ctpool/ tests/
	mypy ctpool/
	pytest
```
Either approach is valid — the requirement is that a single command catches lint, type, and
test failures. Do not ship code where lint and type checks must be run separately.

### Framework

- `pytest` as the sole test runner. Do not use `unittest.TestCase`.
- `pytest-asyncio` for all async test cases with `asyncio_mode = "auto"`.
- `pytest-mock` for mocking.
- Fixtures for all shared setup. Do not duplicate setup code across test functions.
- `@pytest.mark.parametrize` for testing multiple input variations of the same behavior.
- `pytest-cov` for coverage measurement.

### Mock policy

- Mock at system boundaries: HTTP calls (use `respx` or `pytest-httpx` for `httpx`),
  database sessions (use transaction-scoped rollback fixtures).
- Do not mock internal module functions or business logic.
- Do not call real CT log HTTP endpoints in tests.
- Do **not** use SQLite as a test database substitute. The schema uses PostgreSQL-specific
  features (`SELECT ... FOR UPDATE SKIP LOCKED`, `gen_random_uuid()`, UUID primary keys,
  `TIMESTAMPTZ`) that are incompatible with SQLite. Tests that touch the database must use
  the real PostgreSQL instance already running inside the Dev Container.
- Create a dedicated test database: `ctpool_test`. The `test_settings` fixture must override
  `DATABASE_URL` to point to `postgresql+psycopg://ctpool:ctpool@localhost:5432/ctpool_test`.
  Add creation of this database to `dev-db-init.sh`:
  ```sql
  CREATE DATABASE ctpool_test OWNER ctpool;
  ```
- The `db_session` fixture must wrap each test in a savepoint (nested transaction) and roll
  back to the savepoint after the test, so the test database remains clean between runs
  without requiring a full schema reset. Use SQLAlchemy's `begin_nested()` pattern.

### Test naming

Test names must describe the scenario and expected outcome:
```
CORRECT: test_parse_precert_der_returns_parsed_certificate
CORRECT: test_fetch_entries_429_delegates_to_rate_limiter
CORRECT: test_upsert_existing_hostname_no_duplicate
WRONG:   test_error_case
WRONG:   test_invalid_input
```

### Edge case requirements per test suite

Each test suite must explicitly cover:
- Happy path: expected inputs produce expected outputs.
- Empty/zero input: empty bytes, empty lists, zero counts.
- Boundary values: minimum and maximum of any allowed range.
- Invalid input: wrong type, out-of-range value, malformed data, missing required fields.
- Error paths: what happens when a dependency raises an exception or returns an error.
- Async edge cases: request timeout, partial failure in concurrent operations (where applicable).

---

## 6. Resolved Design Decisions

These questions arose during planning. They are resolved here so the implementing LLM does not
need to ask.

### 6.1 `.devcontainer/` location

**Decision:** `.devcontainer/` lives at the repository root. VS Code's Dev Container
specification requires `devcontainer.json` to be discoverable at the repo root or in a
`.devcontainer/` directory at the root. This is infrastructure metadata, not source code.
It is permitted as an exception to the root-only rule.

### 6.2 `pyproject.toml` layout

**Decision:** Use a standard src-layout with `src/ctpool/` as the project root directory
(containing `pyproject.toml`) and `src/ctpool/ctpool/` as the actual Python package directory
(containing `__init__.py`).

```
src/ctpool/
  pyproject.toml          ← project config, dependencies, tool config
  alembic.ini             ← alembic config
  .env.example            ← documented environment variable template
  scripts/                ← shell scripts for DB management
  migrations/             ← alembic migration env and versions
  tests/                  ← test suite
    conftest.py
    test_config.py
    ...
  ctpool/                 ← Python package (importable as `import ctpool`)
    __init__.py
    cli.py
    config.py
    ...
    models/
      __init__.py
      base.py
      ...
```

This is the standard Python src-layout. The package is installed via `pip install -e .` from
`src/ctpool/`. Internal imports are `from ctpool.config import Settings`, etc.

### 6.3 CT log list source URLs

**Decision:** Ingest from three sources to maximize coverage:

| Source | URL |
|--------|-----|
| Chrome (primary) | `https://www.gstatic.com/ct/log_list/v3/log_list.json` |
| Apple | `https://valid.apple.com/ct/log_list/current_log_list.json` |
| CCADB All Logs | `https://www.ccadb.org/cas/ctlogs` (HTML, parse for log URLs) |

For the initial implementation, implement the Chrome list. Apple and CCADB are future
enhancement. The source URL is a compile-time constant in `log_discovery.py` — it is not
user-configurable and not user-supplied at runtime (SSRF prevention).

### 6.4 `ctpool logs-follow`

**Decision:** `ctpool logs-follow` tails the application's own structured log output —
specifically the Python `logging` module's output streamed with `rich`. It is equivalent to
`tail -f` on the application log, not a CT-log-specific stream. It should show configurable
log levels (`--level info`, `--level debug`) and support filtering by log ID.

### 6.5 CT log authentication

**Decision:** CT logs are public HTTP APIs. No authentication is required for any currently
active CT log. `fetcher.py` does not need an auth mechanism for the initial implementation.
If a future log operator requires a key, add it via a per-log config column and an optional
header injection point.

### 6.6 `scripts/` placement

**Decision:** Scripts that manage the in-container PostgreSQL development database belong at
`src/ctpool/scripts/`. They are part of the `ctpool` sub-project's development setup.

### 6.7 Backfill concurrency model

**Decision:** Support multiple concurrent backfill workers claiming different ranges from the
same database. Use `SELECT ... FOR UPDATE SKIP LOCKED` on `ct_log_backfill_ranges` in the
dispatcher's range-claim query. This allows running multiple backfill workers (e.g., one per
log) without coordination overhead. The `claimed_by` column stores a worker instance
identifier (e.g., hostname + PID) for observability.

---

## 7. Technology Stack

| Concern | Library | Version constraint |
|---------|---------|-------------------|
| CLI | `typer` | `>=0.12` |
| HTTP client | `httpx` | `>=0.27` |
| X.509 parsing | `cryptography` | `>=42` |
| PostgreSQL driver | `psycopg[binary]` (psycopg3) | `>=3.2` |
| ORM | `sqlalchemy[asyncio]` | `>=2.0` |
| Migrations | `alembic` | `>=1.13` |
| Configuration | `pydantic-settings` | `>=2.3` |
| Data validation | `pydantic` | `>=2.7` |
| CLI output | `rich` | `>=13` |
| Registrable domain parsing | `tldextract` | `>=5.1` |
| Linter/formatter | `ruff` | `>=0.5` |
| Type checker | `mypy` | `>=1.10` |
| Test runner | `pytest` | `>=8` |
| Async test support | `pytest-asyncio` | `>=0.23` |
| HTTP mock in tests | `pytest-httpx` | `>=0.30` |
| Mock support | `pytest-mock` | `>=3.14` |
| Coverage | `pytest-cov` | `>=5` |

All versions must be pinned in `pyproject.toml` to their exact minor version (e.g.,
`httpx==0.27.2`) for reproducibility.

---

## 8. Dev Container Specification

### Goal

The Dev Container must be self-contained. A developer should be able to open this repository
in VS Code, reopen in container, and have a fully working Python environment with PostgreSQL
running inside the container — no host-level PostgreSQL install required.

### `.devcontainer/devcontainer.json`

```json
{
  "name": "bitsyscerts-ctpool",
  "build": {
    "dockerfile": "Dockerfile",
    "context": ".."
  },
  "forwardPorts": [5432],
  "postCreateCommand": "bash .devcontainer/post-create.sh",
  "customizations": {
    "vscode": {
      "extensions": [
        "ms-python.python",
        "ms-python.mypy-type-checker",
        "charliermarsh.ruff",
        "mtxr.sqltools",
        "mtxr.sqltools-driver-pg"
      ],
      "settings": {
        "python.defaultInterpreterPath": "/usr/local/bin/python",
        "editor.formatOnSave": true,
        "[python]": {
          "editor.defaultFormatter": "charliermarsh.ruff"
        }
      }
    }
  },
  "remoteEnv": {
    "DATABASE_URL": "postgresql+psycopg://ctpool:ctpool@localhost:5432/ctpool"
  }
}
```

### `.devcontainer/Dockerfile`

Base: `python:3.12-slim`. Install:
- `postgresql` and `postgresql-contrib` (the full server, not just the client).
- `libpq-dev` for psycopg build dependencies.
- `build-essential` for any native extensions.
- Create a non-root user `vscode`.
- Do **not** start PostgreSQL in the Dockerfile — that is `post-create.sh`'s job.

### `.devcontainer/post-create.sh`

Sequence:
1. Initialize PostgreSQL data directory: `pg_createcluster 15 main --start` (or equivalent
   for the distro's PostgreSQL version).
2. Start PostgreSQL: `pg_ctlcluster 15 main start` (or `service postgresql start`).
3. Create role and database:
   ```sql
   CREATE ROLE ctpool WITH LOGIN PASSWORD 'ctpool';
   CREATE DATABASE ctpool OWNER ctpool;
   ```
4. Install the Python package in editable mode: `pip install -e "src/ctpool[dev]"`.
5. Run migrations: `cd src/ctpool && ctpool db-init`.

The PostgreSQL data directory should be in a Docker volume or a path that survives normal
`postCreateCommand` re-runs (not in `/tmp`). A reasonable path is `/var/lib/postgresql/data`
or the default cluster location for the distro.

### Development database scripts (`src/ctpool/scripts/`)

| Script | Purpose |
|--------|---------|
| `dev-db-start.sh` | Start the in-container PostgreSQL service |
| `dev-db-init.sh` | Create the `ctpool` role and database; run `ctpool db-init` |
| `dev-db-status.sh` | Check PostgreSQL connectivity; show current Alembic revision |
| `dev-db-reset.sh` | Drop and recreate the dev database (prompts for confirmation; destructive) |

All scripts must be executable (`chmod +x`) and use `#!/usr/bin/env bash` with `set -euo pipefail`.

---

## 9. Database Schema

### Table: `ct_log_sources`

Stores CT log identity and metadata from the CT log list.

| Column | Type | Notes |
|--------|------|-------|
| `id` | `UUID` | PK, default `gen_random_uuid()` |
| `log_id_b64` | `TEXT` | Base64 log ID from CT log list; unique |
| `operator_name` | `TEXT` | Log operator name (e.g., "Google", "Cloudflare") |
| `description` | `TEXT` | Human-readable log description |
| `url` | `TEXT` | Log base URL (not null, unique) |
| `public_key_b64` | `TEXT` | Base64 DER-encoded log public key |
| `log_state` | `TEXT` | CT log state from log list (e.g., "usable", "retired", "pending") |
| `temporal_shard_start` | `TIMESTAMPTZ` | Start of this log's temporal shard (nullable) |
| `temporal_shard_end` | `TIMESTAMPTZ` | End of this log's temporal shard (nullable) |
| `is_eligible_for_tail` | `BOOLEAN` | Whether to include in tail work |
| `is_eligible_for_backfill` | `BOOLEAN` | Whether to include in backfill work |
| `source_list` | `TEXT` | Which log list this was discovered from (e.g., "chrome") |
| `first_seen_at` | `TIMESTAMPTZ` | When first added to our DB |
| `last_synced_at` | `TIMESTAMPTZ` | When last updated from the log list |

### Table: `ct_log_runtime_state`

One row per CT log. Tracks health and learned behavior.

| Column | Type | Notes |
|--------|------|-------|
| `id` | `UUID` | PK |
| `log_source_id` | `UUID` | FK → `ct_log_sources.id`, unique (1:1) |
| `tree_size` | `BIGINT` | Latest known tree size from `get-sth` |
| `sth_timestamp` | `TIMESTAMPTZ` | Timestamp from the latest Signed Tree Head |
| `health_status` | `TEXT` | One of: `ok`, `degraded`, `error`, `unknown` |
| `last_probe_at` | `TIMESTAMPTZ` | When we last probed `get-sth` |
| `last_success_at` | `TIMESTAMPTZ` | When we last got a successful HTTP response |
| `last_error_at` | `TIMESTAMPTZ` | When we last got an HTTP error |
| `last_error_message` | `TEXT` | Human-readable last error message |
| `current_batch_size` | `INTEGER` | Current fetch batch size |
| `learned_max_batch_size` | `INTEGER` | Maximum batch size achieved without error |
| `backoff_until` | `TIMESTAMPTZ` | Do not fetch this log until after this time |
| `last_429_at` | `TIMESTAMPTZ` | When we last got a 429 from this log |
| `consecutive_failures` | `INTEGER` | Count of consecutive fetch failures |

### Table: `ct_log_tail_cursors`

One row per CT log. Tracks tail worker progress.

| Column | Type | Notes |
|--------|------|-------|
| `id` | `UUID` | PK |
| `log_source_id` | `UUID` | FK → `ct_log_sources.id`, unique (1:1) |
| `next_index` | `BIGINT` | Next log index to fetch in the tail |
| `updated_at` | `TIMESTAMPTZ` | When this cursor was last advanced |

### Table: `ct_log_backfill_ranges`

One row per backfill work unit. Multiple workers can claim different rows.

| Column | Type | Notes |
|--------|------|-------|
| `id` | `UUID` | PK |
| `log_source_id` | `UUID` | FK → `ct_log_sources.id` |
| `start_index` | `BIGINT` | First log index in this range (inclusive) |
| `end_index` | `BIGINT` | Last log index in this range (inclusive) |
| `next_index` | `BIGINT` | Next index to fetch within this range |
| `status` | `TEXT` | One of: `pending`, `in_progress`, `complete`, `failed` |
| `claimed_by` | `TEXT` | Worker identity string (hostname + PID), nullable |
| `claimed_at` | `TIMESTAMPTZ` | When claimed, nullable |
| `completed_at` | `TIMESTAMPTZ` | When marked complete, nullable |
| `created_at` | `TIMESTAMPTZ` | When this range was created |
| `updated_at` | `TIMESTAMPTZ` | When last updated |

### Table: `ct_log_observations`

One row per unique (log, index) pair. Links a certificate to its observation in a specific log.

| Column | Type | Notes |
|--------|------|-------|
| `id` | `UUID` | PK |
| `log_source_id` | `UUID` | FK → `ct_log_sources.id` |
| `log_index` | `BIGINT` | Index in the CT log |
| `certificate_id` | `UUID` | FK → `certificates.id` |
| `observed_at` | `TIMESTAMPTZ` | When we ingested this entry |
| Unique | | `(log_source_id, log_index)` |

### Table: `certificates`

One row per unique certificate or precertificate (deduplicated by SHA-256 fingerprint).

| Column | Type | Notes |
|--------|------|-------|
| `id` | `UUID` | PK |
| `fingerprint_sha256` | `TEXT` | Hex SHA-256 of DER; unique |
| `spki_sha256` | `TEXT` | Hex SHA-256 of SubjectPublicKeyInfo DER |
| `serial_number` | `TEXT` | Hex serial number |
| `issuer_dn` | `TEXT` | Full issuer distinguished name |
| `issuer_common_name` | `TEXT` | Issuer CN component |
| `issuer_organization` | `TEXT` | Issuer O component |
| `subject_dn` | `TEXT` | Full subject distinguished name |
| `subject_common_name` | `TEXT` | Subject CN component |
| `not_before` | `TIMESTAMPTZ` | Certificate validity start |
| `not_after` | `TIMESTAMPTZ` | Certificate validity end |
| `signature_algorithm_oid` | `TEXT` | Signature algorithm OID |
| `signature_algorithm_name` | `TEXT` | Human-readable name (e.g., "sha256WithRSAEncryption") |
| `public_key_algorithm_oid` | `TEXT` | Public key algorithm OID |
| `public_key_algorithm_name` | `TEXT` | Human-readable name (e.g., "RSA", "EC") |
| `public_key_bits_or_curve` | `TEXT` | Key size in bits or EC curve name |
| `is_precertificate` | `BOOLEAN` | True if this is a precert (has CT poison extension) |
| `is_wildcard_present` | `BOOLEAN` | True if any SAN contains a wildcard |
| `san_count` | `INTEGER` | Number of SAN DNS names |
| `first_seen_ct` | `TIMESTAMPTZ` | When first observed in any CT log |
| `last_seen_ct` | `TIMESTAMPTZ` | When last observed in any CT log |

### Table: `hostnames`

One row per unique normalized hostname.

| Column | Type | Notes |
|--------|------|-------|
| `id` | `UUID` | PK |
| `hostname` | `TEXT` | Lowercase FQDN (e.g., `api.example.com`); unique |
| `registrable_domain` | `TEXT` | Registrable domain (e.g., `example.com`) |
| `is_wildcard` | `BOOLEAN` | True if the hostname is a wildcard (starts with `*.`) |
| `first_seen_ct` | `TIMESTAMPTZ` | When first observed in any certificate |
| `last_seen_ct` | `TIMESTAMPTZ` | When last observed in any certificate |
| `latest_cert_fingerprint_sha256` | `TEXT` | Fingerprint of the most recently seen cert containing this hostname |
| `latest_cert_not_before` | `TIMESTAMPTZ` | `not_before` of the most recently seen cert |
| `latest_cert_not_after` | `TIMESTAMPTZ` | `not_after` of the most recently seen cert |

### Table: `certificate_hostnames`

Many-to-many join between certificates and hostnames.

| Column | Type | Notes |
|--------|------|-------|
| `certificate_id` | `UUID` | FK → `certificates.id` |
| `hostname_id` | `UUID` | FK → `hostnames.id` |
| PK | | `(certificate_id, hostname_id)` |

### Table: `ingestion_metrics`

Periodic throughput snapshots per log.

| Column | Type | Notes |
|--------|------|-------|
| `id` | `UUID` | PK |
| `log_source_id` | `UUID` | FK → `ct_log_sources.id` |
| `snapshot_at` | `TIMESTAMPTZ` | When snapshot was taken |
| `window_seconds` | `INTEGER` | Rolling window duration |
| `entries_fetched` | `BIGINT` | Entries fetched in window |
| `entries_parsed` | `BIGINT` | Entries parsed in window |
| `certs_upserted` | `BIGINT` | Certificates upserted in window |
| `hostnames_upserted` | `BIGINT` | Hostnames upserted in window |
| `parse_errors` | `INTEGER` | Parse errors in window |
| `http_429_count` | `INTEGER` | 429 responses received in window |
| `http_5xx_count` | `INTEGER` | 5xx responses received in window |
| `throughput_entries_per_sec` | `NUMERIC` | Calculated throughput |

### Table: `ingestion_errors`

Per-log error log for debugging and monitoring.

| Column | Type | Notes |
|--------|------|-------|
| `id` | `UUID` | PK |
| `log_source_id` | `UUID` | FK → `ct_log_sources.id` |
| `occurred_at` | `TIMESTAMPTZ` | When the error occurred |
| `error_type` | `TEXT` | Short error category (e.g., "parse_error", "fetch_error") |
| `error_message` | `TEXT` | Human-readable description (sanitized, no credentials) |
| `log_index` | `BIGINT` | Log index at the time of error, if applicable |
| `http_status_code` | `INTEGER` | HTTP status code if applicable |

---

## 10. Complete Unit Decomposition

All paths are relative to the repository root. The Python package installs as `ctpool`.

### Package root: `src/ctpool/ctpool/`

---

#### `src/ctpool/ctpool/__init__.py`
**Responsibility:** Re-export the public API surface only; no implementation code.  
**Est. lines:** 10  
**Exports:** `Settings`, `CtPoolError` subclasses, model re-exports  

---

#### `src/ctpool/ctpool/exceptions.py`
**Responsibility:** Define the domain exception hierarchy.  
**Est. lines:** 40  
**Public interface:**
```python
class CtPoolError(Exception): ...
class FetchError(CtPoolError): ...
class ParseError(CtPoolError): ...
class DatabaseError(CtPoolError): ...
class DiskGuardError(CtPoolError): ...
class RateLimitError(CtPoolError): ...
class ConfigurationError(CtPoolError): ...
class DispatcherError(CtPoolError): ...
```

---

#### `src/ctpool/ctpool/config.py`
**Responsibility:** Declare all environment variables as a single validated `pydantic-settings`
model. One singleton instantiation.  
**Est. lines:** 60  
**Public interface:**
```python
class Settings(BaseSettings):
    database_url: PostgresDsn
    ct_backfill_days: int = 180
    ct_tail_interval_seconds: int = 300
    ct_min_free_disk_gb: int = 50
    ct_critical_free_disk_gb: int = 20
    ct_default_batch_size: int = 256
    ct_max_batch_size: int = 1024
    ct_log_list_url: str = "https://www.gstatic.com/ct/log_list/v3/log_list.json"
    ct_http_timeout_seconds: int = 30
    ct_max_retries: int = 5
    ct_backoff_max_seconds: int = 300
    log_level: str = "INFO"

def get_settings() -> Settings: ...   # cached singleton
```

---

#### `src/ctpool/ctpool/models/base.py`
**Responsibility:** Declare the SQLAlchemy `DeclarativeBase` and constraint naming convention.  
**Est. lines:** 20  
**Public interface:**
```python
Base: DeclarativeBase
```

---

#### `src/ctpool/ctpool/models/__init__.py`
**Responsibility:** Re-export all ORM model classes.  
**Est. lines:** 20  

---

#### `src/ctpool/ctpool/models/log_source.py`
**Responsibility:** ORM model for `ct_log_sources`.  
**Est. lines:** 40  
**Public interface:** `class CtLogSource(Base): ...`

---

#### `src/ctpool/ctpool/models/log_runtime_state.py`
**Responsibility:** ORM model for `ct_log_runtime_state`.  
**Est. lines:** 45  
**Public interface:** `class CtLogRuntimeState(Base): ...`

---

#### `src/ctpool/ctpool/models/log_tail_cursor.py`
**Responsibility:** ORM model for `ct_log_tail_cursors`.  
**Est. lines:** 30  
**Public interface:** `class CtLogTailCursor(Base): ...`

---

#### `src/ctpool/ctpool/models/log_backfill_range.py`
**Responsibility:** ORM model for `ct_log_backfill_ranges`.  
**Est. lines:** 40  
**Public interface:** `class CtLogBackfillRange(Base): ...`

---

#### `src/ctpool/ctpool/models/observation.py`
**Responsibility:** ORM model for `ct_log_observations`.  
**Est. lines:** 35  
**Public interface:** `class CtLogObservation(Base): ...`

---

#### `src/ctpool/ctpool/models/certificate.py`
**Responsibility:** ORM model for `certificates`.  
**Est. lines:** 45  
**Public interface:** `class Certificate(Base): ...`

---

#### `src/ctpool/ctpool/models/hostname.py`
**Responsibility:** ORM model for `hostnames`.  
**Est. lines:** 30  
**Public interface:** `class Hostname(Base): ...`

---

#### `src/ctpool/ctpool/models/certificate_hostname.py`
**Responsibility:** ORM model for `certificate_hostnames` many-to-many join table.  
**Est. lines:** 25  
**Public interface:** `class CertificateHostname(Base): ...`

---

#### `src/ctpool/ctpool/models/ingestion_metric.py`
**Responsibility:** ORM model for `ingestion_metrics`.  
**Est. lines:** 35  
**Public interface:** `class IngestionMetric(Base): ...`

---

#### `src/ctpool/ctpool/models/ingestion_error.py`
**Responsibility:** ORM model for `ingestion_errors`.  
**Est. lines:** 30  
**Public interface:** `class IngestionError(Base): ...`

---

#### `src/ctpool/ctpool/ct_api_schemas.py`
**Responsibility:** Pydantic models for raw CT HTTP API responses.  
**Est. lines:** 65  
**Public interface:**
```python
class SignedTreeHead(BaseModel):
    tree_size: int
    timestamp: int
    sha256_root_hash: str
    tree_head_signature: str

class CtLeafEntry(BaseModel):
    leaf_input: str   # base64
    extra_data: str   # base64

class CtEntriesResponse(BaseModel):
    entries: list[CtLeafEntry]

class CtLogOperator(BaseModel): ...
class CtLogInfo(BaseModel): ...
class CtLogListResponse(BaseModel):
    operators: list[CtLogOperator]
```

---

#### `src/ctpool/ctpool/pipeline_schemas.py`
**Responsibility:** Pydantic models for internal pipeline data transfer objects.  
**Est. lines:** 65  
**Public interface:**
```python
class ParsedCertificate(BaseModel):
    fingerprint_sha256: str
    spki_sha256: str
    serial_number: str
    issuer_dn: str
    issuer_common_name: str | None
    issuer_organization: str | None
    subject_dn: str
    subject_common_name: str | None
    not_before: datetime
    not_after: datetime
    signature_algorithm_oid: str
    signature_algorithm_name: str
    public_key_algorithm_oid: str
    public_key_algorithm_name: str
    public_key_bits_or_curve: str | None
    is_precertificate: bool
    san_dns_names: list[str]

class NormalizedEntry(BaseModel):
    parsed_certificate: ParsedCertificate
    hostnames: list[str]          # lowercase, deduplicated, trailing dot removed
    is_wildcard_present: bool
    log_source_id: uuid.UUID
    log_index: int
```

---

#### `src/ctpool/ctpool/db.py`
**Responsibility:** Create the async SQLAlchemy engine and session factory from settings.  
**Est. lines:** 60  
**Public interface:**
```python
def create_engine(settings: Settings) -> AsyncEngine: ...
def create_session_factory(engine: AsyncEngine) -> async_sessionmaker: ...

# Context manager for a single session
@asynccontextmanager
async def get_session(session_factory: async_sessionmaker) -> AsyncGenerator[AsyncSession, None]: ...
```

---

#### `src/ctpool/ctpool/migration_runner.py`
**Responsibility:** Run Alembic migrations programmatically (upgrade head, get current revision).  
**Est. lines:** 50  
**Public interface:**
```python
async def run_upgrade_head(settings: Settings) -> None: ...
async def get_current_revision(settings: Settings) -> str | None: ...
```

---

#### `src/ctpool/ctpool/disk_guard.py`
**Responsibility:** Check disk utilization against configurable low/critical thresholds.  
**Est. lines:** 50  
**Public interface:**
```python
def is_disk_low(settings: Settings) -> bool: ...
def is_disk_critical(settings: Settings) -> bool: ...
def get_free_disk_gb(path: str = "/") -> float: ...
```

---

#### `src/ctpool/ctpool/rate_limiter.py`
**Responsibility:** Track per-log backoff state; compute delay for 429/5xx with exponential
backoff and jitter.  
**Est. lines:** ~120 ⚠️ (split to `backoff_state.py` + `rate_limiter.py` if > 150 lines)  
**Public interface:**
```python
@dataclass
class BackoffState:
    log_source_id: uuid.UUID
    consecutive_failures: int
    backoff_until: datetime | None
    last_429_at: datetime | None
    current_batch_size: int
    learned_max_batch_size: int

class RateLimiter:
    def handle_429(self, state: BackoffState, retry_after: int | None = None) -> BackoffState: ...
    def handle_5xx(self, state: BackoffState, status_code: int) -> BackoffState: ...
    def handle_success(self, state: BackoffState) -> BackoffState: ...
    def seconds_until_eligible(self, state: BackoffState) -> float: ...
    def is_eligible(self, state: BackoffState) -> bool: ...
```

---

#### `src/ctpool/ctpool/fetcher.py`
**Responsibility:** Async-fetch a batch of CT log entries by index range using httpx.  
**Est. lines:** ~120 ⚠️ (split to `http_client.py` + `fetcher.py` if > 150 lines)  
**Public interface:**
```python
async def fetch_entries(
    log_url: str,
    start: int,
    end: int,
    client: httpx.AsyncClient,
    settings: Settings,
) -> CtEntriesResponse: ...

async def fetch_sth(
    log_url: str,
    client: httpx.AsyncClient,
    settings: Settings,
) -> SignedTreeHead: ...

def build_httpx_client(settings: Settings) -> httpx.AsyncClient: ...
```

---

#### `src/ctpool/ctpool/parser.py`
**Responsibility:** Decode base64 leaf_input, dispatch to leaf cert or precert parser, return
structured `ParsedCertificate`.  
**Est. lines:** ~130 ⚠️ (pre-approved split: `leaf_cert_parser.py` + `precert_parser.py` +
`parser.py` as 30-line dispatcher if > 150 lines)  

**Critical: RFC 6962 `leaf_input` binary format.** The `leaf_input` field is NOT a raw DER
certificate. It is a TLS-encoded `MerkleTreeLeaf` structure (RFC 6962 §3.4):

```
struct {
    Version     version;         // 1 byte  — must be 0x00 (v1)
    MerkleLeafType leaf_type;    // 1 byte  — 0x00 = timestamped_entry
    TimestampedEntry entry;
} MerkleTreeLeaf;

struct {
    uint64 timestamp;            // 8 bytes, big-endian milliseconds since epoch
    LogEntryType entry_type;     // 2 bytes — 0x0000 = x509_entry, 0x0001 = precert_entry
    select(entry_type) {
        case x509_entry:    ASN.1Cert;     // 3-byte length prefix + DER bytes
        case precert_entry: PreCert;       // issuer_key_hash (32 bytes) +
                                          // 3-byte length + TBSCertificate DER
    }
    CtExtensions extensions;     // 2-byte length prefix + bytes (may be empty)
} TimestampedEntry;
```

The parser must:
1. Base64-decode `leaf_input` to bytes.
2. Read byte 0 (version = 0x00) and byte 1 (leaf_type = 0x00).
3. Skip bytes 2–9 (timestamp — optionally extract for `first_seen_ct`).
4. Read bytes 10–11 (entry_type): `0x0000` = leaf cert, `0x0001` = precert.
5. For `x509_entry`: read 3-byte big-endian length, then that many bytes as DER → parse with
   `x509.load_der_x509_certificate()`.
6. For `precert_entry`: skip 32-byte `issuer_key_hash`, read 3-byte length, then that many
   bytes as `TBSCertificate` DER → parse with `x509.load_der_x509_certificate()`. The
   `extra_data` field (not `leaf_input`) contains the full issuer chain for precerts.

`ParsedCertificate.is_precertificate` should also be detected by the presence of the CT
poison extension OID `1.3.6.1.4.1.11129.2.4.3` in the parsed certificate extensions, which
serves as a second cross-check.

**Public interface:**
```python
def parse_leaf_entry(leaf_input_b64: str) -> ParsedCertificate: ...
# Internal helpers (also independently testable):
def _decode_merkle_leaf(raw: bytes) -> tuple[int, bytes]:  # returns (entry_type, cert_der)
def _parse_leaf_cert_der(der: bytes) -> ParsedCertificate: ...
def _parse_precert_der(der: bytes) -> ParsedCertificate: ...
def _extract_fingerprint_sha256(der: bytes) -> str: ...
def _extract_spki_sha256(cert: x509.Certificate) -> str: ...
```

---

#### `src/ctpool/ctpool/normalizer.py`
**Responsibility:** Extract SAN DNS names from a `ParsedCertificate`, normalize hostnames,
build `NormalizedEntry`.  
**Est. lines:** 80  
**Public interface:**
```python
def normalize_hostnames(san_dns_names: list[str]) -> list[str]: ...
def extract_registrable_domain(hostname: str) -> str: ...
def build_normalized_entry(
    parsed: ParsedCertificate,
    log_source_id: uuid.UUID,
    log_index: int,
) -> NormalizedEntry: ...
```

---

#### `src/ctpool/ctpool/cert_writer.py`
**Responsibility:** Upsert `Certificate`, `Hostname`, and `CertificateHostname` rows
idempotently into PostgreSQL.  
**Est. lines:** 100  
**Public interface:**
```python
async def upsert_certificate(
    session: AsyncSession,
    parsed: ParsedCertificate,
) -> uuid.UUID: ...   # returns certificate.id

async def upsert_hostname(
    session: AsyncSession,
    hostname: str,
    certificate: Certificate,
) -> uuid.UUID: ...   # returns hostname.id

async def upsert_certificate_hostname(
    session: AsyncSession,
    certificate_id: uuid.UUID,
    hostname_id: uuid.UUID,
) -> None: ...
```

---

#### `src/ctpool/ctpool/observation_writer.py`
**Responsibility:** Upsert `CtLogObservation` rows idempotently.  
**Est. lines:** 60  
**Public interface:**
```python
async def upsert_observation(
    session: AsyncSession,
    log_source_id: uuid.UUID,
    log_index: int,
    certificate_id: uuid.UUID,
) -> None: ...
```

---

#### `src/ctpool/ctpool/writer.py`
**Responsibility:** Coordinate the full write pipeline: cert_writer → observation_writer in a
single database transaction.  
**Est. lines:** 50  
**Public interface:**
```python
async def write_normalized_entry(
    session: AsyncSession,
    entry: NormalizedEntry,
) -> None: ...
```

---

#### `src/ctpool/ctpool/metrics.py`
**Responsibility:** Record per-log runtime metrics (throughput counters, error counts, backoff
events) and persist periodic snapshots to the database.  
**Est. lines:** 80  
**Public interface:**
```python
class LogMetricsAccumulator:
    def record_entries_fetched(self, count: int) -> None: ...
    def record_entries_parsed(self, count: int) -> None: ...
    def record_certs_upserted(self, count: int) -> None: ...
    def record_hostnames_upserted(self, count: int) -> None: ...
    def record_parse_error(self) -> None: ...
    def record_http_429(self) -> None: ...
    def record_http_5xx(self) -> None: ...
    def get_snapshot(self, window_seconds: int = 60) -> dict[str, int | float]: ...
    async def persist_snapshot(self, session: AsyncSession, log_source_id: uuid.UUID) -> None: ...
```

---

#### `src/ctpool/ctpool/log_discovery.py`
**Responsibility:** Fetch the CT log list from the Chrome JSON source and upsert `CtLogSource`
rows into the database.  
**Est. lines:** ~120 ⚠️ (split to `log_list_fetcher.py` + `log_source_upsert.py` if > 150 lines)  
**Public interface:**
```python
async def fetch_log_list(
    client: httpx.AsyncClient,
    settings: Settings,
) -> CtLogListResponse: ...

async def sync_log_sources(
    session: AsyncSession,
    log_list: CtLogListResponse,
) -> tuple[int, int]: ...   # (inserted_count, updated_count)
```

---

#### `src/ctpool/ctpool/log_prober.py`
**Responsibility:** Probe a CT log's `get-sth` endpoint and update its `CtLogRuntimeState`.  
**Est. lines:** 80  
**Public interface:**
```python
async def probe_log(
    log_source: CtLogSource,
    client: httpx.AsyncClient,
    session: AsyncSession,
    settings: Settings,
) -> CtLogRuntimeState: ...
```

---

#### `src/ctpool/ctpool/dispatcher.py`
**Responsibility:** Evaluate log eligibility; create, claim, and advance backfill ranges and
tail cursors.  
**Est. lines:** 100  
**Public interface:**
```python
async def get_eligible_tail_logs(session: AsyncSession) -> list[CtLogSource]: ...
async def get_eligible_backfill_logs(session: AsyncSession) -> list[CtLogSource]: ...
async def ensure_tail_cursor(session: AsyncSession, log_source_id: uuid.UUID) -> CtLogTailCursor: ...
async def advance_tail_cursor(session: AsyncSession, log_source_id: uuid.UUID, next_index: int) -> None: ...
async def create_backfill_ranges(
    session: AsyncSession,
    log_source: CtLogSource,
    start_index: int,
    end_index: int,
    chunk_size: int = 10_000,
) -> int: ...   # returns number of ranges created
async def claim_backfill_range(
    session: AsyncSession,
    log_source_id: uuid.UUID | None,
    worker_id: str,
) -> CtLogBackfillRange | None: ...   # uses SELECT FOR UPDATE SKIP LOCKED
async def mark_range_complete(session: AsyncSession, range_id: uuid.UUID) -> None: ...
async def mark_range_failed(session: AsyncSession, range_id: uuid.UUID, reason: str) -> None: ...
```

---

#### `src/ctpool/ctpool/stats.py`
**Responsibility:** Query the database and render per-log ingestion statistics as a Rich
console table.  
**Est. lines:** 100  
**Public interface:**
```python
async def render_stats(session: AsyncSession, console: Console) -> None: ...
async def render_stats_watch(session_factory: async_sessionmaker, console: Console, interval_seconds: int = 5) -> None: ...
```

---

#### `src/ctpool/ctpool/tail_worker.py`
**Responsibility:** Tail loop: for each eligible log, fetch entries from cursor, parse,
write, advance cursor, sleep between intervals.  
**Est. lines:** 100  
**Public interface:**
```python
async def run_tail(
    session_factory: async_sessionmaker,
    settings: Settings,
    once: bool = False,
    limit: int | None = None,
    log_id: uuid.UUID | None = None,
) -> None: ...
```

---

#### `src/ctpool/ctpool/backfill_worker.py`
**Responsibility:** Backfill loop: claim an open range, fetch entries, parse, write, mark done,
repeat.  
**Est. lines:** ~120 ⚠️ (split to `range_processor.py` + `backfill_worker.py` if > 150 lines)  
**Public interface:**
```python
async def run_backfill(
    session_factory: async_sessionmaker,
    settings: Settings,
    once: bool = False,
    limit: int | None = None,
    days: int | None = None,
    log_id: uuid.UUID | None = None,
) -> None: ...
```

---

#### `src/ctpool/ctpool/cli.py`
**Responsibility:** Declare all Typer subcommands with their parameters; delegate immediately
to worker/service functions. No business logic.  
**Est. lines:** 90  
**Commands:** `db-init`, `db-status`, `sync-logs`, `tail`, `backfill`, `stats`, `logs-follow`

---

## 11. Dependency Graph

```
                      stdlib / third-party only
                               │
        ┌──────────┬───────────┼──────────────┐
        │          │           │              │
   exceptions   config    models/base     disk_guard
        │          │           │              │
        │          ├───────────┤              │
        │          │           │              │
        │          db      [all models]       │
        │          │           │              │
        │    ct_api_schemas   pipeline_schemas │
        │          │                          │
        ├──────────┤                          │
        │    rate_limiter                     │
        │          │                          │
        │       fetcher                       │
        │          │                          │
        │        parser                       │
        │          │                          │
        │      normalizer                     │
        │          │                          │
        │    log_discovery   cert_writer       │
        │    log_prober  observation_writer   │
        │    dispatcher      metrics          │
        │                          │          │
        │                       writer        │
        │                       stats         │
        └──────────────────────────┼──────────┘
                                   │
                     tail_worker / backfill_worker
                                   │
                                 cli
```

---

## 12. Bottom-Up Build Order

Build units in this exact sequence. Tests must pass at each tier before the next tier begins.

### Tier 0 — Pure primitives (no internal project dependencies)

1. `ctpool/exceptions.py`
2. `ctpool/config.py`
3. `ctpool/disk_guard.py`
4. `ctpool/models/base.py`
5. `ctpool/ct_api_schemas.py`
6. `ctpool/pipeline_schemas.py`

### Tier 1 — ORM Models (depend only on `models/base.py`)

7. `ctpool/models/log_source.py`
8. `ctpool/models/log_runtime_state.py`
9. `ctpool/models/log_tail_cursor.py`
10. `ctpool/models/log_backfill_range.py`
11. `ctpool/models/observation.py`
12. `ctpool/models/certificate.py`
13. `ctpool/models/hostname.py`
14. `ctpool/models/certificate_hostname.py`
15. `ctpool/models/ingestion_metric.py`
16. `ctpool/models/ingestion_error.py`
17. `ctpool/models/__init__.py`

### Tier 2 — Infrastructure (depend on Tier 0–1)

18. `ctpool/db.py`
19. `ctpool/migration_runner.py`
20. `ctpool/rate_limiter.py`

### Tier 3 — Core I/O and data transformation (depend on Tier 0–2)

21. `ctpool/fetcher.py`
22. `ctpool/parser.py`
23. `ctpool/normalizer.py`

### Tier 4 — Database writers and log management (depend on Tier 0–3)

24. `ctpool/cert_writer.py`
25. `ctpool/observation_writer.py`
26. `ctpool/metrics.py`
27. `ctpool/log_discovery.py`
28. `ctpool/log_prober.py`
29. `ctpool/dispatcher.py`

### Tier 5 — Pipeline coordinator and display (depend on Tier 0–4)

30. `ctpool/writer.py`
31. `ctpool/stats.py`

### Tier 6 — Worker loops (depend on Tier 0–5)

32. `ctpool/tail_worker.py`
33. `ctpool/backfill_worker.py`

### Tier 7 — CLI and package surface (depend on Tier 0–6)

34. `ctpool/cli.py`
35. `ctpool/__init__.py`

---

## 13. Infrastructure Files Specification

### `src/ctpool/pyproject.toml`

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "ctpool"
version = "0.1.0"
description = "Certificate Transparency ingestion, indexing, and intelligence CLI"
requires-python = ">=3.12"
dependencies = [
    "typer==0.12.5",
    "httpx==0.27.2",
    "cryptography==42.0.8",
    "psycopg[binary]==3.2.1",
    "sqlalchemy[asyncio]==2.0.31",
    "alembic==1.13.2",
    "pydantic==2.7.4",
    "pydantic-settings==2.3.4",
    "rich==13.7.1",
    "tldextract==5.1.2",
]

[project.optional-dependencies]
dev = [
    "pytest==8.3.2",
    "pytest-asyncio==0.23.8",
    "pytest-httpx==0.30.0",
    "pytest-mock==3.14.0",
    "pytest-cov==5.0.0",
    "pytest-ruff==0.4.1",
    "pytest-mypy==0.10.3",
    "ruff==0.5.7",
    "mypy==1.10.1",
]

[project.scripts]
ctpool = "ctpool.cli:app"

[tool.hatch.build.targets.wheel]
packages = ["ctpool"]

[tool.ruff]
target-version = "py312"
line-length = 88

[tool.ruff.lint]
select = ["E", "F", "I", "N", "W", "UP", "S", "B", "A", "C4", "PTH"]
ignore = []

[tool.mypy]
python_version = "3.12"
strict = true
warn_return_any = true
warn_unused_configs = true

[tool.pytest.ini_options]
asyncio_mode = "auto"
addopts = "--ruff --mypy --cov=ctpool --cov-report=term-missing --cov-fail-under=75"

[tool.coverage.run]
source = ["ctpool"]
branch = true

[tool.coverage.report]
fail_under = 75
show_missing = true
```

### `src/ctpool/alembic.ini`

Standard Alembic config. Key settings:
- `script_location = migrations`
- `sqlalchemy.url` should be left blank (read from env at runtime via `migrations/env.py`).
- `prepend_sys_path = .`

### `src/ctpool/migrations/env.py`

This file must:
- Import all ORM models **explicitly** to ensure they are registered with `Base.metadata`
  before Alembic autogenerates migrations. Use individual imports, not a wildcard:
  ```python
  from ctpool.models.log_source import CtLogSource
  from ctpool.models.log_runtime_state import CtLogRuntimeState
  from ctpool.models.log_tail_cursor import CtLogTailCursor
  from ctpool.models.log_backfill_range import CtLogBackfillRange
  from ctpool.models.observation import CtLogObservation
  from ctpool.models.certificate import Certificate
  from ctpool.models.hostname import Hostname
  from ctpool.models.certificate_hostname import CertificateHostname
  from ctpool.models.ingestion_metric import IngestionMetric
  from ctpool.models.ingestion_error import IngestionError
  ```
  Do **not** use `from ctpool.models import *` — wildcard imports are prohibited by the coding
  standards in Section 3. The `models/__init__.py` re-exports are for application code; the
  migration env must use direct imports to guarantee module-level side effects.
- Read the database URL from `Settings` (not from `alembic.ini`).
- Support async migration execution (use `run_async_migrations()` pattern from Alembic docs).
- Import `Base` and pass `Base.metadata` as the `target_metadata`.

### `src/ctpool/.env.example`

```env
# Required
DATABASE_URL=postgresql+psycopg://ctpool:ctpool@localhost:5432/ctpool

# Ingestion behavior
CT_BACKFILL_DAYS=180
CT_TAIL_INTERVAL_SECONDS=300
CT_DEFAULT_BATCH_SIZE=256
CT_MAX_BATCH_SIZE=1024

# Disk safety
CT_MIN_FREE_DISK_GB=50
CT_CRITICAL_FREE_DISK_GB=20

# HTTP behavior
CT_HTTP_TIMEOUT_SECONDS=30
CT_MAX_RETRIES=5
CT_BACKOFF_MAX_SECONDS=300

# Logging
LOG_LEVEL=INFO
```

---

## 14. Complete Test Plan

Test files live in `src/ctpool/tests/`. The test discovery path is configured in
`pyproject.toml` so that `pytest` run from `src/ctpool/` finds all tests.

### `tests/conftest.py` — Shared Fixtures

Must provide:
- `test_settings` — `Settings` instance with test values (uses in-memory or test DB).
- `async_engine` — `AsyncEngine` created from `test_settings`.
- `db_session` — `AsyncSession` fixture that wraps each test in a transaction and rolls back
  on teardown (never commits to the real database).
- `mock_httpx_client` — `AsyncMock` of `httpx.AsyncClient`.
- `sample_leaf_cert_der` — raw bytes of a real or synthetic X.509 DER certificate.
- `sample_precert_der` — raw bytes of a real or synthetic precertificate DER (with CT poison).
- `ct_log_source_factory` — creates a `CtLogSource` ORM object with sensible defaults.
- `worker_id` — a consistent test worker identity string.

### `tests/test_exceptions.py`

| Test name | Scenario |
|-----------|---------|
| `test_ct_pool_error_is_base_class` | All custom exceptions inherit from `CtPoolError` |
| `test_fetch_error_is_subclass_of_ct_pool_error` | `FetchError` is a `CtPoolError` |
| `test_parse_error_carries_message` | `ParseError("msg")` preserves the message |
| `test_database_error_chains_original_exception` | `DatabaseError` wraps the original via `__cause__` |
| `test_disk_guard_error_is_ct_pool_error` | `DiskGuardError` is a `CtPoolError` |

### `tests/test_config.py`

| Test name | Scenario |
|-----------|---------|
| `test_loads_all_required_fields_from_env` | All fields load correctly from env |
| `test_missing_database_url_raises_validation_error` | Missing `DATABASE_URL` raises `ValidationError` |
| `test_default_backfill_days_is_180` | Default `ct_backfill_days` is 180 |
| `test_default_tail_interval_is_300` | Default `ct_tail_interval_seconds` is 300 |
| `test_invalid_database_url_raises_validation_error` | Non-postgresql URL is rejected |
| `test_get_settings_returns_singleton` | Two calls to `get_settings()` return the same object |

### `tests/test_disk_guard.py`

| Test name | Scenario |
|-----------|---------|
| `test_is_disk_low_true_when_free_below_threshold` | Returns `True` when free GB < low threshold |
| `test_is_disk_low_false_when_free_above_threshold` | Returns `False` when free GB > low threshold |
| `test_is_disk_critical_true_when_free_below_critical` | Returns `True` when free GB < critical threshold |
| `test_is_disk_critical_false_when_free_above_critical` | Returns `False` when free GB > critical threshold |
| `test_get_free_disk_gb_returns_positive_float` | Returns a positive number for an existing path |
| `test_get_free_disk_gb_nonexistent_path_raises_disk_guard_error` | Raises `DiskGuardError` for bad path |

### `tests/test_models.py`

| Test name | Scenario |
|-----------|---------|
| `test_declarative_base_creates_metadata` | `Base.metadata` is not None |
| `test_naming_convention_applied_to_indexes` | Index naming convention uses `ix_` prefix |
| `test_ct_log_source_has_url_column` | `CtLogSource.url` column exists |
| `test_ct_log_source_url_is_unique` | `CtLogSource.url` has a unique constraint |
| `test_certificate_fingerprint_sha256_is_unique` | `Certificate.fingerprint_sha256` is unique |
| `test_observation_composite_unique_log_id_and_index` | `(log_source_id, log_index)` is unique in observations |
| `test_certificate_hostname_composite_pk` | `(certificate_id, hostname_id)` is the PK |
| `test_backfill_range_status_has_pending_value` | Status enum/column accepts `"pending"` |
| `test_tail_cursor_fk_to_log_source` | `CtLogTailCursor.log_source_id` is an FK |

### `tests/test_ct_api_schemas.py`

| Test name | Scenario |
|-----------|---------|
| `test_signed_tree_head_parses_valid_json` | Valid STH JSON produces `SignedTreeHead` |
| `test_signed_tree_head_missing_tree_size_raises` | Missing `tree_size` raises `ValidationError` |
| `test_ct_entries_response_parses_entry_list` | Valid entries response parses correctly |
| `test_ct_leaf_entry_requires_leaf_input` | Missing `leaf_input` raises `ValidationError` |
| `test_log_list_response_parses_chrome_format` | Chrome log list JSON parses correctly |
| `test_log_list_response_empty_operators_allowed` | Empty operators list is valid |

### `tests/test_pipeline_schemas.py`

| Test name | Scenario |
|-----------|---------|
| `test_parsed_certificate_requires_fingerprint_sha256` | Missing fingerprint raises `ValidationError` |
| `test_normalized_entry_hostnames_is_list` | `hostnames` field is a `list[str]` |
| `test_normalized_entry_allows_empty_hostname_list` | Empty hostnames list is valid |
| `test_parsed_certificate_not_before_is_datetime` | `not_before` is a `datetime` |
| `test_normalized_entry_is_wildcard_present_false_by_default` | Default is `False` |

### `tests/test_db.py`

| Test name | Scenario |
|-----------|---------|
| `test_create_engine_returns_async_engine` | Returns an `AsyncEngine` instance |
| `test_session_factory_yields_async_session` | Session factory produces `AsyncSession` |
| `test_session_rolls_back_on_exception` | Exception in session body triggers rollback |
| `test_engine_uses_database_url_from_settings` | Engine connection string matches settings |

### `tests/test_migration_runner.py`

| Test name | Scenario |
|-----------|---------|
| `test_run_upgrade_head_succeeds` | Runs without raising on a fresh test DB |
| `test_run_upgrade_idempotent_when_already_at_head` | Running twice does not error |
| `test_get_current_revision_returns_string_after_upgrade` | Returns a revision string post-upgrade |
| `test_get_current_revision_returns_none_on_empty_db` | Returns `None` on uninitialized DB |

### `tests/test_rate_limiter.py`

| Test name | Scenario |
|-----------|---------|
| `test_initial_state_has_no_delay` | Fresh `BackoffState` is immediately eligible |
| `test_handle_429_sets_backoff` | After 429, `seconds_until_eligible` > 0 |
| `test_retry_after_header_is_respected` | `Retry-After: 60` sets at least 60s backoff |
| `test_handle_5xx_sets_backoff` | After 5xx, `seconds_until_eligible` > 0 |
| `test_consecutive_failures_increase_delay_exponentially` | Delay doubles with each failure |
| `test_jitter_adds_randomization` | Two calls with same state do not produce identical delays |
| `test_successful_response_resets_consecutive_failures` | Success clears `consecutive_failures` |
| `test_delay_does_not_exceed_configured_maximum` | Delay caps at `ct_backoff_max_seconds` |
| `test_batch_size_decreases_on_429` | Batch size halves (minimum 1) on 429 |
| `test_batch_size_recovers_toward_max_on_success` | Batch size increases toward `learned_max_batch_size` |
| `test_batch_size_minimum_is_one` | Repeated 429s cannot reduce batch size below 1 |

### `tests/test_fetcher.py`

| Test name | Scenario |
|-----------|---------|
| `test_fetch_entries_returns_correct_count` | Returns the expected number of entries |
| `test_fetch_entries_passes_start_and_end_params` | Correct query params sent to log URL |
| `test_fetch_entries_429_raises_rate_limit_error` | HTTP 429 raises `RateLimitError` |
| `test_fetch_entries_5xx_raises_fetch_error` | HTTP 500 raises `FetchError` |
| `test_fetch_entries_network_error_raises_fetch_error` | Network timeout raises `FetchError` |
| `test_fetch_entries_empty_response_returns_empty_list` | `{"entries": []}` returns empty list |
| `test_fetch_entries_invalid_json_raises_fetch_error` | Non-JSON response raises `FetchError` |
| `test_fetch_sth_returns_signed_tree_head` | Valid STH response returns `SignedTreeHead` |
| `test_fetch_sth_invalid_response_raises_fetch_error` | Invalid STH JSON raises `FetchError` |

### `tests/test_parser.py`

| Test name | Scenario |
|-----------|---------|
| `test_parse_leaf_cert_der_returns_parsed_certificate` | Valid DER leaf cert parses completely |
| `test_parse_precert_der_returns_parsed_certificate` | Valid precert DER parses with `is_precertificate=True` |
| `test_fingerprint_sha256_is_hex_string_of_correct_length` | 64-char hex string |
| `test_not_before_and_not_after_are_datetimes` | Both validity fields are `datetime` |
| `test_issuer_cn_extracted_from_issuer_dn` | Issuer CN matches expected value |
| `test_subject_cn_extracted_from_subject_dn` | Subject CN matches expected value |
| `test_malformed_der_raises_parse_error` | Random bytes raises `ParseError` |
| `test_empty_bytes_raises_parse_error` | Empty bytes raises `ParseError` |
| `test_cert_with_no_san_extension_does_not_raise` | Missing SAN yields empty `san_dns_names` |
| `test_precert_poison_extension_detected` | CT poison OID triggers `is_precertificate=True` |
| `test_base64_decoding_failure_raises_parse_error` | Invalid base64 raises `ParseError` |

### `tests/test_normalizer.py`

| Test name | Scenario |
|-----------|---------|
| `test_extract_dns_sans_from_parsed_certificate` | DNS SANs become hostnames |
| `test_wildcard_san_included_in_hostnames` | `*.example.com` is retained |
| `test_ip_sans_are_not_included` | IP address SANs are excluded (hostname normalization only) |
| `test_hostname_normalized_to_lowercase` | Mixed-case hostname is lowercased |
| `test_trailing_dot_removed` | `example.com.` becomes `example.com` |
| `test_empty_san_list_returns_empty_hostnames` | No SANs → empty hostname list |
| `test_build_normalized_entry_sets_is_wildcard_present` | `True` when any hostname is wildcard |
| `test_build_normalized_entry_sets_is_wildcard_false` | `False` when no wildcard hostnames |
| `test_duplicate_hostnames_deduplicated` | Same hostname in SAN twice → one entry |

### `tests/test_cert_writer.py`

| Test name | Scenario |
|-----------|---------|
| `test_upsert_certificate_inserts_new_row` | New fingerprint creates a row |
| `test_upsert_certificate_no_duplicate_on_conflict` | Same fingerprint is idempotent |
| `test_upsert_certificate_returns_existing_id` | Second upsert returns same UUID |
| `test_upsert_hostname_inserts_new_row` | New hostname creates a row |
| `test_upsert_hostname_no_duplicate_on_conflict` | Same hostname is idempotent |
| `test_upsert_certificate_hostname_creates_join` | Join row is created |
| `test_upsert_certificate_hostname_idempotent` | Duplicate join upsert does not raise |
| `test_all_hostnames_in_normalized_entry_are_linked` | Multiple hostnames all get join rows |

### `tests/test_observation_writer.py`

| Test name | Scenario |
|-----------|---------|
| `test_upsert_observation_inserts_new_row` | New (log_id, index) creates a row |
| `test_upsert_observation_no_duplicate_on_conflict` | Same (log_id, index) is idempotent |
| `test_observation_links_correct_certificate_id` | FK matches the cert |
| `test_observation_links_correct_log_source_id` | FK matches the log source |

### `tests/test_writer.py`

| Test name | Scenario |
|-----------|---------|
| `test_write_normalized_entry_calls_cert_writer` | `cert_writer.upsert_certificate` is called |
| `test_write_normalized_entry_calls_observation_writer` | `observation_writer.upsert_observation` is called |
| `test_write_normalized_entry_idempotent_on_second_call` | Second write of same entry does not error |
| `test_write_normalized_entry_with_precert_succeeds` | Precert entry writes correctly |
| `test_db_error_propagates_as_database_error` | SQLAlchemy error is wrapped in `DatabaseError` |

### `tests/test_metrics.py`

| Test name | Scenario |
|-----------|---------|
| `test_record_entries_fetched_increments_counter` | Counter increases by the correct amount |
| `test_record_parse_error_increments_error_counter` | Error counter increments |
| `test_record_http_429_increments_429_counter` | 429 counter increments |
| `test_get_snapshot_returns_correct_structure` | Snapshot has all expected keys |
| `test_throughput_calculated_over_rolling_window` | Throughput uses recent window, not lifetime |
| `test_persist_snapshot_writes_to_db` | `IngestionMetric` row is created |

### `tests/test_log_discovery.py`

| Test name | Scenario |
|-----------|---------|
| `test_fetch_log_list_returns_parsed_response` | Valid Chrome JSON returns `CtLogListResponse` |
| `test_fetch_log_list_http_error_raises_fetch_error` | HTTP 500 raises `FetchError` |
| `test_fetch_log_list_invalid_json_raises_parse_error` | Non-JSON body raises `ParseError` |
| `test_sync_log_sources_inserts_new_log` | New log URL creates a `CtLogSource` row |
| `test_sync_log_sources_updates_existing_log` | Existing log URL updates metadata |
| `test_sync_log_sources_returns_correct_counts` | Returns `(inserted, updated)` tuple |
| `test_empty_operator_list_returns_zero_counts` | Empty log list does nothing |

### `tests/test_log_prober.py`

| Test name | Scenario |
|-----------|---------|
| `test_probe_healthy_log_updates_tree_size` | Successful STH updates `tree_size` |
| `test_probe_healthy_log_sets_status_ok` | Status becomes `"ok"` |
| `test_probe_http_timeout_marks_state_error` | Timeout sets `health_status="error"` |
| `test_probe_http_500_marks_state_error` | 5xx sets `health_status="error"` |
| `test_probe_invalid_sth_response_raises_fetch_error` | Invalid STH JSON raises |
| `test_probe_updates_last_probe_at_timestamp` | `last_probe_at` is updated |

### `tests/test_dispatcher.py`

| Test name | Scenario |
|-----------|---------|
| `test_get_eligible_tail_logs_excludes_ineligible` | Only `is_eligible_for_tail=True` logs returned |
| `test_get_eligible_backfill_logs_excludes_ineligible` | Only `is_eligible_for_backfill=True` logs returned |
| `test_ensure_tail_cursor_creates_if_missing` | Creates cursor with `next_index=0` |
| `test_ensure_tail_cursor_returns_existing` | Returns existing cursor without modification |
| `test_advance_tail_cursor_updates_next_index` | `next_index` is updated to new value |
| `test_advance_tail_cursor_is_idempotent_on_same_value` | Same value does not error |
| `test_create_backfill_ranges_creates_correct_count` | Range count = ceil((end-start)/chunk_size) |
| `test_claim_range_transitions_to_in_progress` | Status changes from `pending` to `in_progress` |
| `test_claim_range_returns_none_when_all_claimed` | Returns `None` with no pending ranges |
| `test_claim_range_sets_claimed_by_worker_id` | `claimed_by` matches the worker ID |
| `test_mark_range_complete_transitions_to_complete` | Status changes to `complete` |
| `test_mark_range_failed_transitions_to_failed` | Status changes to `failed` |

### `tests/test_stats.py`

| Test name | Scenario |
|-----------|---------|
| `test_render_stats_produces_output` | No exception raised; output is non-empty |
| `test_render_stats_includes_active_log_names` | Active log URLs appear in output |
| `test_render_stats_shows_entry_count` | Entry count column is present |
| `test_render_stats_shows_error_count` | Error count column is present |
| `test_render_stats_empty_database_renders_gracefully` | Empty DB renders without error |

### `tests/test_tail_worker.py`

| Test name | Scenario |
|-----------|---------|
| `test_tail_worker_advances_cursor_on_success` | `next_index` advances by entries fetched |
| `test_tail_worker_pauses_when_disk_is_low` | Low disk → no fetch attempt |
| `test_tail_worker_exits_after_one_iteration_with_once_flag` | `once=True` exits after first iteration |
| `test_tail_worker_stops_at_entry_limit` | `limit=10` stops after 10 entries |
| `test_tail_worker_sleeps_on_empty_response` | Empty entries response → sleep without advancing cursor |
| `test_tail_worker_logs_error_and_continues_on_fetch_failure` | `FetchError` is caught and logged |
| `test_tail_worker_filter_restricts_to_single_log_id` | `log_id` parameter limits to one log |
| `test_tail_worker_records_metrics_after_each_batch` | Metrics accumulator is called |

### `tests/test_backfill_worker.py`

| Test name | Scenario |
|-----------|---------|
| `test_backfill_worker_claims_and_processes_range` | Claims range, fetches, writes, marks done |
| `test_backfill_worker_marks_range_done_on_success` | Range status becomes `complete` |
| `test_backfill_worker_pauses_when_disk_is_low` | Low disk → pauses before fetch |
| `test_backfill_worker_halts_when_disk_is_critical` | Critical disk → halts all work |
| `test_backfill_worker_exits_after_one_iteration_with_once_flag` | `once=True` exits after first range |
| `test_backfill_worker_exits_at_entry_limit` | `limit=100` stops after 100 entries |
| `test_backfill_worker_exits_when_no_pending_ranges` | No ranges → clean exit |
| `test_backfill_worker_filter_restricts_to_single_log_id` | `log_id` parameter limits scope |
| `test_backfill_worker_records_metrics_per_batch` | Metrics accumulator is called per batch |

### `tests/test_cli.py`

| Test name | Scenario |
|-----------|---------|
| `test_db_init_command_invokes_migration_runner` | `ctpool db-init` calls `run_upgrade_head` |
| `test_db_status_command_shows_revision` | `ctpool db-status` outputs current revision |
| `test_sync_logs_command_invokes_discovery_and_prober` | `ctpool sync-logs` calls fetch and probe |
| `test_tail_command_invokes_tail_worker` | `ctpool tail` calls `run_tail` |
| `test_tail_command_passes_once_flag` | `ctpool tail --once` passes `once=True` |
| `test_tail_command_passes_limit` | `ctpool tail --limit 100` passes `limit=100` |
| `test_backfill_command_invokes_backfill_worker` | `ctpool backfill` calls `run_backfill` |
| `test_stats_command_invokes_stats_display` | `ctpool stats` calls `render_stats` |
| `test_unknown_subcommand_exits_nonzero` | `ctpool nonexistent` exits with non-zero code |

---

## 15. CLI Specification

The CLI entry point is `ctpool` (defined in `pyproject.toml` `[project.scripts]`).

### Command: `ctpool db-init`
Initialize the database by running Alembic migrations to `head`.

### Command: `ctpool db-status`
Show the current database URL (redacted), current Alembic revision, and whether the schema is
up to date.

### Command: `ctpool sync-logs`
1. Fetch CT log list from the Chrome log list URL.
2. Upsert `CtLogSource` rows.
3. Probe each eligible log with `get-sth`.
4. Update `CtLogRuntimeState` for each.
5. Print a summary (logs discovered, inserted, updated, healthy, degraded, error).

### Command: `ctpool tail [OPTIONS]`

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--once` | flag | False | Run one iteration then exit |
| `--limit` | int | None | Stop after processing this many entries |
| `--log-id` | UUID | None | Restrict to a single CT log |

### Command: `ctpool backfill [OPTIONS]`

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--once` | flag | False | Process one range then exit |
| `--limit` | int | None | Stop after processing this many entries |
| `--days` | int | None | Override CT_BACKFILL_DAYS for this run |
| `--log-id` | UUID | None | Restrict to a single CT log |

### Command: `ctpool stats [OPTIONS]`

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--watch` | flag | False | Refresh the stats table every 5 seconds |

Display (per log):
- Log URL (truncated)
- Health status
- Tree size
- Tail lag (tree_size - tail_next_index)
- Backfill progress (% and ETA)
- Entries/sec (rolling 60s window)
- Certs/sec (rolling 60s window)
- Parse errors
- HTTP 429 count
- HTTP 5xx count
- Backoff state (eligible / backoff until \<time\>)
- Disk free (GB)

### Command: `ctpool logs-follow [OPTIONS]`

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--level` | str | "INFO" | Minimum log level to display |
| `--log-id` | UUID | None | Filter to messages from a specific CT log |

Streams the application's structured `logging` output to the terminal using Rich formatting.

---

## 16. Configuration Reference

All configuration is loaded from environment variables via `pydantic-settings`. The `.env`
file at `src/ctpool/.env` (git-ignored) overrides environment for local development.

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `DATABASE_URL` | str | **required** | PostgreSQL async DSN: `postgresql+psycopg://user:pass@host:port/db` |
| `CT_BACKFILL_DAYS` | int | `180` | Lookback window for backfill |
| `CT_TAIL_INTERVAL_SECONDS` | int | `300` | Sleep between tail iterations |
| `CT_MIN_FREE_DISK_GB` | int | `50` | Pause backfill when free disk < this |
| `CT_CRITICAL_FREE_DISK_GB` | int | `20` | Pause all ingestion when free disk < this |
| `CT_DEFAULT_BATCH_SIZE` | int | `256` | Initial CT log entry fetch batch size |
| `CT_MAX_BATCH_SIZE` | int | `1024` | Maximum batch size |
| `CT_LOG_LIST_URL` | str | Chrome URL | CT log list JSON URL |
| `CT_HTTP_TIMEOUT_SECONDS` | int | `30` | HTTP request timeout |
| `CT_MAX_RETRIES` | int | `5` | Maximum retries before giving up on a request |
| `CT_BACKOFF_MAX_SECONDS` | int | `300` | Maximum backoff delay |
| `LOG_LEVEL` | str | `"INFO"` | Python logging level |

---

## 17. Operational Behavior Reference

### Idempotence guarantee

All ingestion writes use `INSERT ... ON CONFLICT DO NOTHING` or
`INSERT ... ON CONFLICT (...) DO UPDATE` as appropriate:

- `certificates`: conflict on `fingerprint_sha256`
- `hostnames`: conflict on `hostname`
- `certificate_hostnames`: conflict on `(certificate_id, hostname_id)` — DO NOTHING
- `ct_log_observations`: conflict on `(log_source_id, log_index)` — DO NOTHING

Reprocessing any range is always safe. Duplicate entries create no logical duplicates.

### Rate limit behavior

On HTTP 429:
1. Check for `Retry-After` header. If present and valid, set `backoff_until = now + retry_after_seconds`.
2. If absent, use exponential backoff: `delay = min(base * 2^n + jitter, max_backoff)`.
3. Halve the current batch size (minimum 1).
4. Record the event in metrics.
5. Do not let one log's rate limiting stall other logs.

On HTTP 5xx:
1. Use exponential backoff with jitter.
2. Record the error in `ingestion_errors`.
3. Retry up to `CT_MAX_RETRIES` times before marking the log as degraded.

On sustained success:
1. Cautiously increase batch size: `new_size = min(current * 1.1, learned_max, CT_MAX_BATCH_SIZE)`.

### Disk safety behavior

```
free_disk_gb >= CT_MIN_FREE_DISK_GB:
    → tail and backfill may run normally

CT_CRITICAL_FREE_DISK_GB <= free_disk_gb < CT_MIN_FREE_DISK_GB:
    → pause backfill
    → continue tail
    → log a warning

free_disk_gb < CT_CRITICAL_FREE_DISK_GB:
    → pause both tail and backfill
    → log a critical alert
    → `ctpool stats` shows the critical state clearly
```

### Backfill range creation

To create backfill ranges for a log:
1. Get current `tree_size` from `CtLogRuntimeState`.
2. Compute approximate start index for the configured lookback window. Since CT logs are
   index-based (not date-queryable), find the approximate start by binary-searching entries
   for the `not_before` timestamp closest to `now - CT_BACKFILL_DAYS`. A coarser approximation
   (sampling every 1000 entries) is acceptable for the initial implementation.
3. Divide `[start_index, tree_size - 1]` into chunks of 10,000 entries each.
4. Insert each chunk as a `ct_log_backfill_range` row with status `pending`.
5. If ranges already exist for this log (from a previous run), skip range creation for
   already-covered index windows.

### Tail worker loop

```python
# Pseudocode — implement properly with async/await
for log in await dispatcher.get_eligible_tail_logs(session):
    if disk_guard.is_disk_critical(settings):
        log.warning("Critical disk space; skipping tail")
        continue
    cursor = await dispatcher.ensure_tail_cursor(session, log.id)
    sth = await fetcher.fetch_sth(log.url, client, settings)
    if sth.tree_size <= cursor.next_index:
        continue  # nothing new
    end_index = min(sth.tree_size - 1, cursor.next_index + batch_size - 1)
    entries = await fetcher.fetch_entries(log.url, cursor.next_index, end_index, client, settings)
    for entry in entries.entries:
        parsed = parser.parse_leaf_entry(entry.leaf_input)
        normalized = normalizer.build_normalized_entry(parsed, log.id, cursor.next_index + i)
        await writer.write_normalized_entry(session, normalized)
    await dispatcher.advance_tail_cursor(session, log.id, cursor.next_index + len(entries.entries))
    await session.commit()
```

### Backfill worker loop

```python
# Pseudocode
worker_id = f"{socket.gethostname()}-{os.getpid()}"
while True:
    if disk_guard.is_disk_critical(settings):
        log.critical("Critical disk; halting backfill")
        break
    if disk_guard.is_disk_low(settings):
        log.warning("Low disk; pausing backfill")
        await asyncio.sleep(60)
        continue
    range_ = await dispatcher.claim_backfill_range(session, log_id, worker_id)
    if range_ is None:
        break  # no work available
    # process range: fetch, parse, write, advance range.next_index, commit
    await dispatcher.mark_range_complete(session, range_.id)
    if once:
        break
```

---

## 18. Implementation Checklist

Work through this checklist in order. Check each item only after the implementation file
**and** its test file both exist and tests pass.

### Phase 1 — Scaffolding

- [ ] Create `.devcontainer/Dockerfile`
- [ ] Create `.devcontainer/devcontainer.json`
- [ ] Create `.devcontainer/post-create.sh`
- [ ] Create `src/ctpool/pyproject.toml`
- [ ] Create `src/ctpool/alembic.ini`
- [ ] Create `src/ctpool/.env.example`
- [ ] Create `src/ctpool/scripts/dev-db-start.sh`
- [ ] Create `src/ctpool/scripts/dev-db-init.sh`
- [ ] Create `src/ctpool/scripts/dev-db-status.sh`
- [ ] Create `src/ctpool/scripts/dev-db-reset.sh`
- [ ] Create `src/ctpool/tests/conftest.py`
- [ ] Create `src/ctpool/migrations/env.py`
- [ ] Create `src/ctpool/migrations/versions/.gitkeep`

### Phase 2 — Tier 0 Primitives

- [ ] `exceptions.py` + `test_exceptions.py` + tests pass
- [ ] `config.py` + `test_config.py` + tests pass
- [ ] `disk_guard.py` + `test_disk_guard.py` + tests pass
- [ ] `models/base.py` (tested via models integration)
- [ ] `ct_api_schemas.py` + `test_ct_api_schemas.py` + tests pass
- [ ] `pipeline_schemas.py` + `test_pipeline_schemas.py` + tests pass

### Phase 3 — Tier 1 ORM Models

- [ ] All 10 model files + `models/__init__.py` + `test_models.py` + tests pass
- [ ] First Alembic migration generated (`alembic revision --autogenerate -m "initial schema"`)
- [ ] Migration applies cleanly (`ctpool db-init`)

### Phase 4 — Tier 2 Infrastructure

- [ ] `db.py` + `test_db.py` + tests pass
- [ ] `migration_runner.py` + `test_migration_runner.py` + tests pass
- [ ] `rate_limiter.py` + `test_rate_limiter.py` + tests pass

### Phase 5 — Tier 3 Core I/O

- [ ] `fetcher.py` + `test_fetcher.py` + tests pass
- [ ] `parser.py` + `test_parser.py` + tests pass
- [ ] `normalizer.py` + `test_normalizer.py` + tests pass

### Phase 6 — Tier 4 Writers and Log Management

- [ ] `cert_writer.py` + `test_cert_writer.py` + tests pass
- [ ] `observation_writer.py` + `test_observation_writer.py` + tests pass
- [ ] `metrics.py` + `test_metrics.py` + tests pass
- [ ] `log_discovery.py` + `test_log_discovery.py` + tests pass
- [ ] `log_prober.py` + `test_log_prober.py` + tests pass
- [ ] `dispatcher.py` + `test_dispatcher.py` + tests pass

### Phase 7 — Tier 5 Coordinator and Display

- [ ] `writer.py` + `test_writer.py` + tests pass
- [ ] `stats.py` + `test_stats.py` + tests pass

### Phase 8 — Tier 6 Workers

- [ ] `tail_worker.py` + `test_tail_worker.py` + tests pass
- [ ] `backfill_worker.py` + `test_backfill_worker.py` + tests pass

### Phase 9 — Tier 7 CLI and Package

- [ ] `cli.py` + `test_cli.py` + tests pass
- [ ] `__init__.py`

### Phase 10 — Final Validation

- [ ] `pytest` from `src/ctpool/` — all tests pass, no lint errors, no type errors
- [ ] Coverage report: statements ≥ 75%, branches ≥ 75%, functions ≥ 75%, lines ≥ 75%
- [ ] `ctpool db-init` runs cleanly inside the Dev Container
- [ ] `ctpool sync-logs` discovers and stores CT log metadata
- [ ] `ctpool tail --once --limit 10` fetches 10 entries and exits
- [ ] `ctpool stats` shows a correctly formatted output
- [ ] `ctpool backfill --once --limit 100` processes one range and exits

---

*End of INITIAL_PLAN.md*
