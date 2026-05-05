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

## Repository layout

```
src/
  api/      # Python · FastAPI · PostgreSQL — query and pivot API
  app/      # React · Vite · Mantine — reference UI
  ctpool/   # Python CLI — CT log ingestion pipeline
```

See [AGENTS.md](AGENTS.md) for repository-wide coding mandates and engineering guardrails.
See [INITIAL_PLAN.md](INITIAL_PLAN.md) for the full architecture, schema, and implementation plan.
