# Product Requirements Document — BitsysCerts

> [!NOTE]
> This document describes the product as it is designed and built. It is not a roadmap.
> Unimplemented capabilities are marked **Future** and are outside the current scope.

---

## Table of Contents

- [Product Vision](#product-vision)
- [Target Users](#target-users)
- [Core Use Cases](#core-use-cases)
- [Functional Requirements](#functional-requirements)
- [Retention Model](#retention-model)
- [Non-Goals](#non-goals)
- [Integration Boundaries](#integration-boundaries)
- [Deployment Model](#deployment-model)
- [Success Criteria](#success-criteria)
- [Glossary](#glossary)

---

## Product Vision

BitsysCerts is a **self-hostable Certificate Transparency indexing and enrichment platform**
for security research, CTI, bug bounty, OSINT, and investigative workflows.

It ingests CT log streams, normalises the data, and exposes it through a queryable REST API
and a lightweight reference web UI. The product is designed to answer practical questions
about CT-observed hostnames and certificate metadata — not to mirror the complete historical
state of the internet's public CT ecosystem, and not to provide real-time enterprise
monitoring guarantees.

> [!IMPORTANT]
> CT data is evidence that a hostname appeared in a publicly logged certificate. It is
> **not** proof that the hostname currently resolves, is reachable, or is controlled by
> the same party today. BitsysCerts surfaces CT-derived enrichment, not authoritative
> DNS inventory.

> [!NOTE]
> BitsysCerts is complementary to tools like `crt.sh`, not a replacement. Its default
> `current-osint` profile retains a rolling window of fresh signal — not complete CT
> history. This is a deliberate design constraint, not a limitation to be worked around.

---

## Target Users

| User | Role | Primary Need |
|---|---|---|
| Security researcher | Individual / team | CT-derived hostname discovery and certificate pivot for targets; local, private queries |
| Bug bounty hunter | Individual | Enumerate CT-observed hostnames for in-scope registered domains |
| Red team / penetration tester | Individual / team | Certificate-derived attack surface enrichment; recently issued certificate discovery |
| Threat intelligence analyst | SOC / MSSP / CTI team | Enrich suspicious infrastructure indicators with CT-derived certificate metadata |
| OSINT investigator | Individual | Pivot from a hostname or fingerprint through locally indexed CT data |
| Platform / tooling engineer | Developer | Consume a private CT enrichment API from custom tooling without third-party rate limits |
| Self-hoster | Individual | Run a private CT-derived index without sending queries to external services |

---

## Core Use Cases

### UC-1: CT-Observed Hostname Discovery

**Actor:** Security researcher  
**Goal:** Find CT-observed hostnames for a given registered domain.

**Query patterns:**

| Pattern | Meaning |
|---|---|
| `example.com` | Exact match on hostname |
| `*.example.com` | CT-observed hostnames under `example.com` |
| `re:^api\..*\.example\.com$` | Regex match against hostname |
| `example.com` + `recursive=true` | All CT-observed hostnames sharing the same registrable domain |

**Expected output:** Paginated list of hostnames with first/last CT observation timestamps
and latest certificate summary.

---

### UC-2: Certificate Metadata Lookup

**Actor:** Security researcher, threat intelligence analyst  
**Goal:** Retrieve full certificate metadata for a known SHA-256 fingerprint.

**Input:** `GET /v1/certificates/{fingerprint_sha256}`

**Expected output:** Full certificate record including issuer, subject, validity window,
Subject Alternative Names, key algorithm, precertificate flag, and all known hostnames
that referenced this certificate.

---

### UC-3: CT-Observed Hostname Discovery with Depth Control

**Actor:** Penetration tester  
**Goal:** Find CT-observed hostnames at a specific label depth under a domain.

**Example:** Find third-level CT-observed hostnames under `example.com` (e.g.,
`api.example.com`, `www.example.com`) without returning fourth-level names.

**Query:** `q=*.example.com&depth=3&recursive=false`

> [!NOTE]
> Results reflect CT observations. They are not a complete inventory of all DNS names
> that exist or have ever existed for the domain.

---

### UC-4: Operational Dashboard

**Actor:** Self-hoster, platform engineer  
**Goal:** Monitor CT ingestion health, storage consumption, and backfill progress at a
glance without querying the database directly.

**Dashboard surfaces:**

- Total hostname and certificate counts
- Worker activity (per-worker status, assigned log, heartbeat)
- Per-log backfill state (status, checkpoint, window, progress) — primary
  backfill health source under default per-log dispatch
- Per-CT-log tail position and ingestion rate
- Database contention metrics (deadlock rate, adaptive batch sizing)
- Storage usage by table
- Active storage profile and retention windows
- Legacy range status and audit findings — surfaced under an
  Advanced / Legacy section; not primary operator workflow

---

### UC-5: Storage Profile Management

**Actor:** Self-hoster  
**Goal:** Switch between retention profiles to control storage consumption and data
richness without redeploying.

**Profiles:**

| Profile | Storage class | Notes |
|---|---|---|
| `current-osint` | GB-class | **Default.** Fresh OSINT; rolling retention windows |
| `research` | GB–TB-class | Longer lookback; richer metadata |
| `archive` | TB-class+ | Full CT archival; **must be explicitly enabled** |

---

### UC-6: API Integration

**Actor:** Custom security tooling, automation pipelines, or any REST API consumer  
**Goal:** Query BitsysCerts programmatically for CT-derived hostname and certificate
enrichment from a private, locally-controlled index.

**Interface:** OpenAPI-described REST API at `/v1/`. Interactive documentation at `/docs`.

> [!NOTE]
> BitsysCerts exposes a product API over locally indexed CT-derived data. This API is not
> the CT log protocol itself — CT log protocol behaviour is used on the ingestion side only.

---

## Functional Requirements

### Ingestion (ctpool)

| ID | Requirement | Priority |
|---|---|---|
| ING-1 | Fetch and normalise the public CT log list from the Google CT Log List API | Must |
| ING-2 | Tail each eligible CT log from its current tree size at a configurable interval | Must |
| ING-3 | Backfill CT logs from a configurable lookback window (default: 30 days) | Must |
| ING-4 | Parse X.509 and precertificate entries; extract SANs, issuer, subject, fingerprints | Must |
| ING-5 | Deduplicate certificates by SHA-256 fingerprint | Must |
| ING-6 | Maintain durable hostname state (first/last seen) with upsert semantics | Must |
| ING-7 | Honour disk-space guard thresholds; abort ingestion before disk exhaustion | Must |
| ING-8 | Adaptive batch sizing under database contention using EMA smoothing | Should |
| ING-9 | Expose data-integrity audit checks with automated repair strategies | Should |
| ING-10 | Support configurable retention pruning for all bounded tables | Must |

### API (certsapi)

| ID | Requirement | Priority |
|---|---|---|
| API-1 | `GET /v1/hostnames` — hostname search with cursor-based pagination | Must |
| API-2 | Support exact, wildcard (`*.domain`), regex (`re:pattern`), and recursive search modes | Must |
| API-3 | `GET /v1/certificates/{fingerprint_sha256}` — full certificate detail by fingerprint | Must |
| API-4 | `GET /v1/stats` — ingestion and storage statistics from cached snapshots | Must |
| API-5 | `GET/PUT /v1/settings/storage` — read and update active storage configuration | Must |
| API-6 | `GET /health` — liveness probe for orchestrators | Must |
| API-7 | Interactive OpenAPI documentation at `/docs` (Scalar) | Should |
| API-8 | All query parameters validated with Pydantic before database access | Must |
| API-9 | Cursor-based pagination (keyset); no offset-based pagination | Must |
| API-10 | Stats endpoint returns from a cached snapshot; never blocks on a live aggregate query | Must |

### Frontend (app)

| ID | Requirement | Priority |
|---|---|---|
| UI-1 | Dashboard page with live-refreshing (10 s) ingestion and storage metrics | Must |
| UI-2 | Hostname search page with query input, filter controls, and paginated results | Must |
| UI-3 | Detail drawer for hostname and certificate detail | Must |
| UI-4 | Settings page for storage profile management | Must |
| UI-5 | Dark / light mode toggle | Should |
| UI-6 | Responsive layout usable on desktop and tablet | Should |
| UI-7 | Accessible interactive elements (ARIA labels, keyboard navigation) | Must |
| UI-8 | Error boundaries on all pages with meaningful fallback UI | Must |

---

## Retention Model

BitsysCerts uses a tiered retention model controlled by the active storage profile. All
ingestion code must honour the active profile.

```mermaid
flowchart TD
    A[CT Log Entry Received] --> B{Is fingerprint<br/>already known?}
    B -- Yes --> C[Update hostname<br/>last_seen_ct only]
    B -- No --> D[Parse certificate<br/>Extract SANs]
    D --> E[Write certificate<br/>record]
    E --> F[Upsert hostnames<br/>+ relationships]
    F --> G[Write ct_entry_outcome]
    G --> H{Retention profile?}
    H -- current-osint --> I[Rolling 12-month<br/>cert retention]
    H -- research --> J[Extended lookback<br/>configurable window]
    H -- archive --> K[Full retention<br/>explicit opt-in only]
    I & J & K --> L[Prune job<br/>enforces window]
```

### Data Retention by Class

| Data Class | `current-osint` | `research` | `archive` |
|---|---|---|---|
| Hostname state | Indefinite | Indefinite | Indefinite |
| Certificate records | Rolling 12 months | Configurable | Indefinite |
| CT entry outcomes | 30–180 days | Configurable | Configurable |
| Backfill range metadata | Until completed | Until completed | Until completed |
| Stats snapshots | Configurable | Configurable | Configurable |
| Raw certificates / chains | Not retained | Optional | Optional |
| Public key material | Not retained | Not retained | Optional |

> [!CAUTION]
> The `archive` profile requires explicit deployment configuration. Any code path that
> activates archive behaviour without explicit configuration is a defect.

---

## Non-Goals

The following are explicitly out of scope. Proposals that conflict with this list will be
rejected unless accompanied by an Architectural Decision Record (ADR) that revises scope.

- **Four-nines availability or enterprise SLA guarantees.** BitsysCerts is a self-hosted
  research tool, not a managed monitoring service.
- **Up-to-the-second certificate alerting.** CT tail lag is expected; freshness is
  best-effort and depends on operator configuration.
- **Authoritative DNS or asset inventory.** CT data reflects certificate observations,
  not current DNS state.
- **Mirroring every CT log forever.** BitsysCerts retains a rolling window by default,
  not a complete archive.
- **Retaining every certificate ever observed.** Deduplication and retention pruning are
  required design constraints.
- **Retaining every duplicate CT log entry.** Entry outcomes are bounded and pruned.
- **Reconstructing the full historical certificate state of the internet.** This is a
  TB-class concern requiring explicit ADR and opt-in configuration.
- **Storing full public key material by default.** Key material is not retained in the
  default profile.
- **Becoming a general-purpose internet archive.**
- **Multi-region enterprise deployment architecture.** Horizontal scale-out and HA
  clustering are outside the project roadmap.
- **Replacing every historical use case of `crt.sh`.** BitsysCerts is complementary and
  present-focused.

---

## Integration Boundaries

```mermaid
graph LR
    CT[Public CT Logs] -->|HTTP fetch| ctpool
    ctpool -->|writes| PG[(PostgreSQL 17)]
    PG -->|reads| api[certsapi / FastAPI]
    api -->|REST /v1/| app[React App]
    api -->|REST /v1/| ext[External Consumers / Custom Tooling]
```

BitsysCerts exposes one interface: the REST API at `/v1/`. All consumers — the reference
UI, automation pipelines, and any downstream tooling — use the same interface. There is no
separate internal API or shared-library integration.

BitsysCerts provides CT-derived enrichment. DNS resolution, live TLS inspection, and
current reachability are separate evidence streams and are not part of this product.

---

## Deployment Model

BitsysCerts is distributed as a Docker Compose stack. See [docs/ARCHITECTURE.md](ARCHITECTURE.md)
for the full deployment topology.

**Minimum viable self-hosted configuration:**

| Component | Requirement |
|---|---|
| CPU | 2 cores |
| RAM | 4 GB |
| Disk | 50 GB SSD (GB-class `current-osint` profile) |
| OS | Any Docker-capable Linux host |
| Network | Outbound HTTPS to CT log URLs |

> [!TIP]
> For the `research` profile, plan for 200 GB+ of disk. For `archive`, plan for TB-class
> storage and consult the deployment documentation before proceeding.

---

## Freshness and Completeness

BitsysCerts is designed to be useful even when not perfectly caught up.

Depending on storage profile, worker count, log availability, network speed, rate limits,
and disk performance, an instance may be minutes, hours, or days behind some CT logs.
This is expected for self-hosted deployments and is not a defect.

The operator dashboard exposes tail lag, backfill progress, failed ranges, audit findings,
storage projections, and worker health so operators can understand the quality and
freshness of their local index. BitsysCerts should be treated as a **best-effort enrichment
source**, not a guaranteed complete or real-time authority.

---

## Success Criteria

| Metric | Target |
|---|---|
| Hostname search response time (p95) | < 200 ms |
| Stats endpoint response time (p95) | < 50 ms (served from snapshot cache) |
| CT tail freshness (best-effort) | Typically within the `CT_TAIL_INTERVAL_SECONDS` polling window of the log's current tree size |
| Test coverage | ≥ 75% statements, branches, functions, lines (all sub-projects) |
| Storage growth rate (`current-osint`) | Predictable GB-class; monitored via storage metrics endpoint |

---

## Glossary

| Term | Definition |
|---|---|
| **CT** | Certificate Transparency — an open, auditable log of publicly trusted X.509 certificates |
| **CT log** | A public append-only Merkle tree operated by a log operator (Google, Let's Encrypt, DigiCert, etc.) |
| **Precertificate** | A draft certificate submitted to a CT log before the final certificate is issued |
| **SAN** | Subject Alternative Name — an X.509 extension listing all hostnames a certificate covers |
| **Fingerprint (SHA-256)** | The SHA-256 hash of a DER-encoded certificate, used as a stable unique identifier |
| **SPKI SHA-256** | The SHA-256 hash of the Subject Public Key Info structure |
| **Registrable domain** | The effective TLD+1 component of a hostname (e.g., `example.com` from `api.example.com`) |
| **Tail cursor** | The current CT log tree index up to which entries have been fetched by the tail worker |
| **Per-log backfill state** | The current dispatch model: each CT log has one row in `ct_log_backfill_state` tracking checkpoint, window, claim, and status. Default since Sprint 1B. |
| **Backfill range** | Legacy concept: a contiguous slice of CT log entry indices stored in `ct_log_backfill_ranges`. Retained for compatibility with the legacy dispatcher and audit/repair workflows; not primary in default per-log dispatch. |
| **Storage profile** | A named configuration (`current-osint`, `research`, `archive`) that controls retention windows and data richness |
| **OSINT** | Open Source Intelligence — intelligence gathered from publicly available sources |
