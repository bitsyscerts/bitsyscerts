# BitsysCerts

[![CI](https://github.com/bitsyscerts/bitsyscerts/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/bitsyscerts/bitsyscerts/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/bitsyscerts/bitsyscerts/branch/main/graph/badge.svg)](https://codecov.io/gh/bitsyscerts/bitsyscerts)
[![Latest release](https://img.shields.io/github/v/release/bitsyscerts/bitsyscerts?label=latest)](https://github.com/bitsyscerts/bitsyscerts/releases/latest)
[![Open issues](https://img.shields.io/github/issues/bitsyscerts/bitsyscerts)](https://github.com/bitsyscerts/bitsyscerts/issues)
[![Open PRs](https://img.shields.io/github/issues-pr/bitsyscerts/bitsyscerts)](https://github.com/bitsyscerts/bitsyscerts/pulls)

[![bitsyscerts-api](https://img.shields.io/github/v/release/bitsyscerts/bitsyscerts?label=bitsyscerts-api&logo=docker&color=0ea5e9)](https://github.com/bitsyscerts/bitsyscerts/pkgs/container/bitsyscerts-api)
[![bitsyscerts-app](https://img.shields.io/github/v/release/bitsyscerts/bitsyscerts?label=bitsyscerts-app&logo=docker&color=0ea5e9)](https://github.com/bitsyscerts/bitsyscerts/pkgs/container/bitsyscerts-app)

**A self-hostable Certificate Transparency indexing and enrichment platform for security
research, CTI, bug bounty, OSINT, and investigative workflows.**

> Certificate Transparency enrichment without depending on `crt.sh`.

---

## What It Is

BitsysCerts continuously ingests public Certificate Transparency (CT) log streams,
normalises the data, and makes it queryable through a REST API and a lightweight web UI.

It is designed for operators who want a **private, locally-controlled CT-derived hostname
and certificate intelligence index** — without sending queries to third-party services.

CT data is evidence that a hostname appeared in a publicly logged certificate. It is
**not** proof that the hostname currently resolves, is reachable, or is still operated by
the same entity. BitsysCerts surfaces CT-observed hostnames and certificate-derived
enrichment — not authoritative DNS inventory.

---

## Intended Use

BitsysCerts is designed for security research, threat intelligence, bug bounty, OSINT,
and investigative enrichment workflows.

It is useful when you have a domain, hostname, certificate fingerprint, or suspicious
infrastructure indicator and want to pivot through locally indexed CT data without
relying on external services.

**Example uses:**

- Discovering CT-observed hostnames for a registrable domain.
- Pivoting from a suspicious FQDN to certificates issued around the same period.
- Finding SAN co-occurrence patterns across CT-observed certificates.
- Enriching DNS, TLS, and OSINT investigations with certificate-derived metadata.
- Running a private CT-derived hostname index for self-hosted security tooling.

> [!IMPORTANT]
> BitsysCerts is **not** a real-time production certificate monitoring service, an
> enterprise SLA-backed CT alerting platform, or an authoritative source of DNS truth.

---

## What It Is Not

- A four-nines enterprise monitoring platform or SLA-backed alerting service.
- An up-to-the-second certificate feed — self-hosted deployments may be minutes, hours,
  or days behind some CT logs depending on storage profile, worker count, and network.
- An authoritative DNS or asset inventory source — CT data shows that a hostname appeared
  in a certificate, not that it currently resolves or is reachable.
- A complete replacement for `crt.sh` — BitsysCerts is a complementary, present-focused,
  self-hosted enrichment tool.
- A full historical CT warehouse by default — the `current-osint` profile retains a
  rolling window, not the complete CT history.

---

## Why Self-Host CT Data

- **Privacy** — hostname and fingerprint queries stay local; nothing is sent to external
  lookup APIs.
- **Speed** — local PostgreSQL queries are faster than round-tripping to a public service.
- **Control** — choose your own retention window, storage profile, and enrichment scope.
- **Integration** — expose the REST API to your own tooling without rate-limit concerns.
- **Offline capability** — once indexed, the data is available even without internet access.

---

## Storage Profiles

BitsysCerts supports multiple storage profiles so operators can choose between disk
usage and retained history. Storage profiles are first-class runtime settings stored
in the database. Environment variables are used only as bootstrap defaults on first
startup.

| Profile | Storage class | Recommended for |
|---|---|---|
| `current-osint` | GB-class | **Default.** Fresh OSINT; rolling retention windows. Start here. |
| `research` | GB–TB-class | Longer lookback; richer certificate metadata for deeper pivots |
| `archive` | TB-class+ | Broad/full retention; **must be explicitly configured** |

The active profile can be changed at runtime via `PUT /v1/settings/storage` or the
Settings page in the UI. Switching profiles does not delete existing data — the next
prune cycle enforces the new retention windows.

> [!TIP]
> First-time operators should start with `current-osint`. It is the most disk-efficient
> profile and suitable for the majority of security research and OSINT workflows.

> [!CAUTION]
> The `archive` profile requires significant storage capacity (TB-class) and must be
> explicitly configured. It is never activated by default.

---

## Freshness and Completeness

BitsysCerts is designed to be useful even when it is not perfectly caught up.

Depending on storage profile, worker count, log availability, network conditions, and
disk performance, an instance may be minutes, hours, or days behind some CT logs. This
is expected for self-hosted deployments and is not a defect.

The operator dashboard exposes tail lag, backfill progress, failed ranges, audit
findings, storage projections, and worker health so operators can understand the quality
and freshness of their local index.

> [!NOTE]
> BitsysCerts should be treated as a best-effort enrichment source, not a guaranteed
> complete or real-time authority.

---

## Quick Start (Self-Hosted)

BitsysCerts ships as a Docker Compose stack. You do not need the source repository on
your server — just three files.

### Requirements

- Linux host with [Docker Engine 25+](https://docs.docker.com/engine/install/) and the
  Compose plugin (`docker compose version` must succeed)
- Outbound HTTPS to public CT log URLs
- Port 80 (or your chosen `FRONTEND_PORT`) reachable from your browser

### 1 — Download the runtime files

```sh
mkdir bitsyscerts && cd bitsyscerts

BASE=https://raw.githubusercontent.com/bitsyscerts/bitsyscerts/main/src
curl -sSfO "${BASE}/docker-compose.yml"
curl -sSfO "${BASE}/.env.example"
curl -sSfO "${BASE}/server-deploy.sh"
chmod +x server-deploy.sh
```

### 2 — Configure

```sh
cp .env.example .env
$EDITOR .env
```

| Variable | Required | Description |
|---|---|---|
| `POSTGRES_PASSWORD` | Yes | Password for the bundled PostgreSQL service |
| `DATABASE_URL` | Yes | Async DSN — use `postgres` as the host; password must match above |
| `IMAGE_TAG` | Yes | GHCR image tag, e.g. `latest` or a pinned version like `26.504.913` |
| `CT_BACKFILL_DAYS` | No | Days of history to backfill on first run (default: `30`) |
| `FRONTEND_PORT` | No | Host port for the web UI (default: `80`) |

> [!NOTE]
> Using the bundled PostgreSQL service? The one-role setup is sufficient. Set
> `DATABASE_ADMIN_URL` only if you are connecting to an external PostgreSQL server
> where the application role does not have database-create privileges.

### 3 — Deploy

```sh
./server-deploy.sh
```

The script:
1. Pulls all images from GHCR
2. Starts PostgreSQL and waits until it is healthy
3. Runs schema migrations
4. Fetches the current CT log list (`ctpool sync-logs`)
5. Brings up the full stack: API, web UI, backfill worker, tail worker

Once it completes, open `http://<your-host>/` in a browser. The dashboard shows ingestion
progress — backfill will run in the background for the configured lookback window.

### Updating

```sh
# Edit IMAGE_TAG in .env to pin a new version (optional), then:
./server-deploy.sh
```

Pass `--skip-migrate` if you know the schema is already current. Pass `--skip-sync-logs`
if the CT log list was recently synced.

---

## API and Integrations

The REST API is available at `http://<your-host>/v1/`. Interactive documentation (Scalar)
is at `http://<your-host>/docs`.

| Endpoint | Description |
|---|---|
| `GET /v1/hostnames` | Search CT-observed hostnames with cursor pagination |
| `GET /v1/certificates/{sha256}` | Full certificate detail by SHA-256 fingerprint |
| `GET /v1/stats` | Ingestion and storage statistics |
| `GET /v1/settings/storage` | Read active retention profile |
| `PUT /v1/settings/storage` | Update retention profile |
| `GET /health` | Liveness probe |

The API follows the OpenAPI 3.1 specification. The schema is at `/openapi.json`.

BitsysCerts exposes a product API over locally indexed CT-derived data. This API is not
the CT log protocol itself — CT log protocol behaviour is used on the ingestion side only.

> [!NOTE]
> CT data reflects public certificate observations and may be historical. Results
> represent CT-observed hostnames, not a complete or current DNS inventory.

---

## Certificate Transparency Stewardship

BitsysCerts is a CT indexer, not a CT log operator.

The ingestion pipeline is designed to read public CT logs respectfully: honouring
per-log rate limits, backing off on HTTP 429, maintaining per-log cursors, and using
bounded concurrency. Operators should tune worker count, retention windows, and storage
profiles responsibly.

See [docs/CT_STEWARDSHIP.md](docs/CT_STEWARDSHIP.md) for the full stewardship policy.

---

## Architecture

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the full system diagram, data flow,
database schema, and deployment topology.

```
src/
  api/      # Python · FastAPI · PostgreSQL — REST API
  app/      # React · Vite · Mantine — web UI
  ctpool/   # Python · Typer — CT ingestion pipeline and CLI
docs/
  PRD.md              # Product requirements and scope
  ARCHITECTURE.md     # System architecture, data flow, deployment topology
  CT_STEWARDSHIP.md   # CT log access policy and stewardship
  STYLE_GUIDE.md      # Code style reference
```

---

## Manual Operations (CLI)

The `ctpool` CLI is available inside the running `api` container for maintenance tasks:

```sh
# Routine per-log runtime checks
docker compose exec api ctpool stats
docker compose exec api ctpool backfill
docker compose exec api ctpool backfill-state

# Routine retention maintenance
docker compose exec api ctpool prune-for-storage-profile

# Advanced / debug legacy compatibility tools
docker compose exec api ctpool legacy-ranges status
docker compose exec api ctpool reap-stale-backfill-claims

# Advanced / debug audit tools
docker compose exec api ctpool check-audit-gaps

# Preview audit repairs
docker compose exec api ctpool fix-audit-findings --dry-run

# Reset migrations and reinitialise (destructive)
docker compose run --rm migrate ctpool init-db --force
```

`ctpool backfill` uses per-log dispatch by default. `legacy-ranges`,
`reap-stale-backfill-claims`, `check-audit-gaps`, and `fix-audit-findings`
are retained for compatibility, troubleshooting, and one-off historical repair.

---

## Contributing

See [.github/CONTRIBUTING.md](.github/CONTRIBUTING.md) for setup instructions, branching
conventions, commit format, and the pull request process.

All contributions must:

- Ship with tests (75% coverage gate on all dimensions)
- Pass `pytest` (Python) and `npm run test` (React) with no linting suppressions
- Follow the [style guide](docs/STYLE_GUIDE.md)

---

## License

[MIT](LICENSE) — free to use, modify, and commercialise. Provided as-is, without warranty.


