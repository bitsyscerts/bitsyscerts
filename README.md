# BitsysCerts

[![CI](https://github.com/bitsyscerts/bitsyscerts/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/bitsyscerts/bitsyscerts/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/bitsyscerts/bitsyscerts/branch/main/graph/badge.svg)](https://codecov.io/gh/bitsyscerts/bitsyscerts)
[![Latest release](https://img.shields.io/github/v/release/bitsyscerts/bitsyscerts?label=latest)](https://github.com/bitsyscerts/bitsyscerts/releases/latest)
[![Open issues](https://img.shields.io/github/issues/bitsyscerts/bitsyscerts)](https://github.com/bitsyscerts/bitsyscerts/issues)
[![Open PRs](https://img.shields.io/github/issues-pr/bitsyscerts/bitsyscerts)](https://github.com/bitsyscerts/bitsyscerts/pulls)

[![bitsyscerts-api](https://img.shields.io/github/v/release/bitsyscerts/bitsyscerts?label=bitsyscerts-api&logo=docker&color=0ea5e9)](https://github.com/bitsyscerts/bitsyscerts/pkgs/container/bitsyscerts-api)
[![bitsyscerts-app](https://img.shields.io/github/v/release/bitsyscerts/bitsyscerts?label=bitsyscerts-app&logo=docker&color=0ea5e9)](https://github.com/bitsyscerts/bitsyscerts/pkgs/container/bitsyscerts-app)

A self-hostable [Certificate Transparency](https://certificate.transparency.dev/) intelligence
service. Run your own CT hostname discovery and certificate lookup service — no third-party
APIs required.

---

## What it does

BitsysCerts continuously ingests public Certificate Transparency log streams, normalises the
data, and makes it queryable through a REST API and a lightweight web UI.

**Ask it questions like:**

- What hostnames and subdomains have recently appeared for `example.com`?
- What certificates has `api.example.com` been seen on?
- What does the full metadata for certificate fingerprint `abc123…` look like?
- What new CT observations have appeared in the last 24 hours?

**Search modes supported:**

| Query | Meaning |
|---|---|
| `example.com` | Exact hostname match |
| `*.example.com` | All subdomains |
| `re:^api\..*\.example\.com$` | Regex match |
| `example.com` + recursive | All hostnames sharing the same registered domain |

> [!NOTE]
> BitsysCerts is **not** a full historical CT mirror. Its default `current-osint` retention
> profile keeps a rolling window of recent signal — not every certificate ever issued.
> This is a deliberate design choice. See [docs/PRD.md](docs/PRD.md) for the full scope.

---

## Quick start (self-hosted)

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
# Edit IMAGE_TAG in .env if you want to pin a new version, then:
./server-deploy.sh
```

Pass `--skip-migrate` if you know the schema is already current. Pass `--skip-sync-logs`
if the CT log list was recently synced.

---

## API

The REST API is available at `http://<your-host>/v1/`. Interactive documentation (Scalar)
is at `http://<your-host>/docs`.

| Endpoint | Description |
|---|---|
| `GET /v1/hostnames` | Search hostnames with cursor pagination |
| `GET /v1/certificates/{sha256}` | Full certificate detail by SHA-256 fingerprint |
| `GET /v1/stats` | Ingestion and storage statistics |
| `GET /v1/settings/storage` | Read active retention profile |
| `PUT /v1/settings/storage` | Update retention profile |
| `GET /health` | Liveness probe |

The API follows the OpenAPI 3.1 specification. The schema is available at `/openapi.json`.

---

## Retention profiles

| Profile | Storage class | Notes |
|---|---|---|
| `current-osint` | GB-class | **Default.** Rolling retention windows; fresh OSINT focus |
| `research` | GB–TB-class | Longer lookback; richer metadata |
| `archive` | TB-class+ | Full CT archival; **must be explicitly configured** |

The active profile can be changed at runtime via `PUT /v1/settings/storage` or the
Settings page in the UI. Switching profiles does not delete existing data — the next
prune cycle enforces the new retention windows.

> [!CAUTION]
> The `archive` profile requires explicit configuration and significant storage capacity.
> It is never activated by default.

---

## What BitsysCerts is not

- A complete replacement for `crt.sh` or a full historical CT archive
- A tool that retains every certificate or every duplicate log entry ever seen
- A TB-class deployment by default (that requires the `archive` profile)

---

## Manual operations (CLI)

The `ctpool` CLI is available inside the running `api` container for maintenance tasks:

```sh
# View ingestion statistics
docker compose exec api ctpool stats

# Run a data integrity audit
docker compose exec api ctpool check-audit-gaps

# Repair audit findings
docker compose exec api ctpool fix-audit-findings

# Manually prune data to the active retention profile
docker compose exec api ctpool prune-for-storage-profile

# Reset migrations and reinitialise (destructive)
docker compose run --rm migrate ctpool init-db --force
```

---

## Repository layout

```
src/
  api/      # Python · FastAPI · PostgreSQL — REST API
  app/      # React · Vite · Mantine — web UI
  ctpool/   # Python · Typer — CT ingestion pipeline and CLI
docs/
  PRD.md          # Product requirements and scope
  ARCHITECTURE.md # System architecture, data flow, deployment topology
  STYLE_GUIDE.md  # Code style reference
```

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

