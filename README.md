# bitsyscerts

A self-hostable Certificate Transparency intelligence service for current hostname discovery,
certificate metadata lookup, and OSINT pivot support.

---

## What BitsysCerts is

BitsysCerts is a **current, query-oriented** Certificate Transparency (CT) intelligence
service. It ingests CT log data, normalises it, and exposes it through a queryable API and
lightweight reference UI designed to answer practical OSINT and reconnaissance questions.

BitsysCerts is **not** a full historical mirror of the public CT ecosystem. Its default
purpose is to retain the latest useful CT signal — not every historical raw certificate,
duplicate log entry, or full certificate chain forever.

---

## Product purpose

BitsysCerts exists to answer practical questions such as:

- **Hostname discovery:** What hostnames and subdomains have recently appeared for a domain?
- **Current exposure:** What names appear to be active or recently issued?
- **Certificate metadata:** What issuer, validity period, Subject Alternative Name
  relationships, and fingerprints are associated with observed names?
- **Pivot support:** What hostnames, registered domains, certificate fingerprints, and Subject
  Alternative Name relationships can be used by BitsysTools and BitsysTrace?
- **Fresh signal:** What new Certificate Transparency observations have appeared recently?

---

## Default retention mode: `current-osint`

BitsysCerts defaults to the `current-osint` retention profile, optimised for current OSINT,
reconnaissance, and hostname discovery.

| Data class | Default retention |
|---|---|
| Hostname state (durable summary) | Indefinite |
| Recent certificate observations | Rolling 12 months |
| SAN co-occurrence relationships | Rolling 12 months |
| Raw CT entry metadata | 30 – 180 days |
| Parsed raw certificate payload | 30 – 180 days (optional) |
| Full raw certificates / chains | **Not retained by default** |
| Public key material | **Not retained by default** |
| Duplicate log sightings | 30 – 180 days |

Additional retention profiles (`research`, `archive`) are available for longer lookback
windows or full archival use cases. The `archive` profile must be explicitly configured and
is a TB-class deployment mode. It is **never the default**.

---

## Integration boundaries

BitsysCerts is a data source for other Bitsys projects. It does not absorb their
functionality.

```
BitsysCerts  →  CT ingestion, normalisation, indexing, querying, reference UI
BitsysTools  →  consumes BitsysCerts CT intelligence for public diagnostics
BitsysTrace  →  consumes BitsysCerts CT intelligence for pivot workflows
```

---

## Non-goals

The following are explicit non-goals for the default BitsysCerts product:

- Mirroring every CT log forever.
- Retaining every certificate ever observed.
- Retaining every duplicate CT log entry.
- Reconstructing the full historical certificate state of the internet.
- Storing full public key material by default.
- Becoming a general-purpose internet archive.
- Replacing every historical feature of `crt.sh`.

---

## Self-hosting: getting started

BitsysCerts is deployed as a set of Docker images pulled from GHCR. You do not need the
source repository on your server.

### Requirements

- Ubuntu 22.04+ (or any Linux with Docker Engine 25+ and the Compose plugin)
- `docker compose version` must succeed — install with `apt install docker-compose-plugin`
- Ports 80 (or your chosen `FRONTEND_PORT`) open to your network

### First-time setup

**1. Download the three runtime files into a directory of your choice:**

```sh
mkdir bitsyscerts && cd bitsyscerts

BASE=https://raw.githubusercontent.com/bitsyscerts/bitsyscerts/main/src
curl -sSfO "${BASE}/docker-compose.yml"
curl -sSfO "${BASE}/.env.example"
curl -sSfO "${BASE}/server-deploy.sh"
chmod +x server-deploy.sh
```

**2. Configure your environment:**

```sh
cp .env.example .env
$EDITOR .env          # set POSTGRES_PASSWORD, DATABASE_URL, IMAGE_TAG, etc.
```

Minimum required values in `.env`:

| Variable | Description |
|---|---|
| `POSTGRES_PASSWORD` | Password for the bundled PostgreSQL service |
| `DATABASE_URL` | Must match `POSTGRES_PASSWORD` — use `postgres` as the host |
| `IMAGE_TAG` | Tag to pull from GHCR, e.g. `latest` or `26.504.913` |

For the bundled PostgreSQL service, the default one-role setup is sufficient:
the role referenced by `DATABASE_URL` is also the bootstrap role created by the
official `postgres` image, so `ctpool init-db --force` can reset the app DB
without a second DSN. Set `DATABASE_ADMIN_URL` only when using an external or
locked-down PostgreSQL server where the app role does not have database-create
privileges.

**3. Deploy:**

```sh
./server-deploy.sh
```

This script:
1. Pulls all images from GHCR
2. Starts PostgreSQL and waits until it is healthy
3. Runs the compose-native `migrate` service to initialise / migrate the schema
4. Runs `ctpool sync-logs` to fetch the current CT log list
5. Brings up the full stack (API, frontend, backfill worker, tail worker)

If you need to rerun migrations manually outside the wrapper script, use the
compose service directly:

```sh
docker compose up --abort-on-container-exit --exit-code-from migrate migrate
```

If you need to destructively reset the configured application database, run the
same image through the `migrate` service rather than trying to `exec` into a
nonexistent `ctpool` service:

```sh
docker compose run --rm migrate ctpool init-db --force
```

### Re-deploying / updating

```sh
# Update IMAGE_TAG in .env if pinning a specific version, then:
./server-deploy.sh --skip-migrate
```

Pass `--skip-sync-logs` as well if you only changed application config and the CT log list
is already current.

### Pinning to a specific version

Set `IMAGE_TAG` in `.env` to a specific version tag from GHCR, e.g.:

```sh
IMAGE_TAG=26.504.913        # production build from main
IMAGE_TAG=26.504.913-staging-abc1234   # a specific branch build
```

`latest` always points to the most recent `main` build. Branch builds produce a
`latest-<branch>` tag (e.g. `latest-staging`) for convenience.

---

## Repository layout

```
src/
  api/      # Python · FastAPI · PostgreSQL — query and pivot API
  app/      # React · Vite · Mantine — reference UI
  ctpool/   # Python CLI — CT log ingestion pipeline
```

See [AGENTS.md](AGENTS.md) for repository-wide coding mandates and engineering guardrails.
See [INITIAL_PLAN.md](INITIAL_PLAN.md) for the full architecture, schema, and implementation plan.
