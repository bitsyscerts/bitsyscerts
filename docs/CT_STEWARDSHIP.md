# Certificate Transparency Stewardship

BitsysCerts is a CT **indexer**, not a CT **log operator**. This document describes how
the ingestion pipeline accesses public CT logs and what operators are expected to do to
use BitsysCerts responsibly.

---

## What CT Logs Are

Certificate Transparency logs are public, append-only Merkle trees operated by trusted
log operators (Google, Let's Encrypt, DigiCert, Sectigo, and others). They are a public
good relied upon by the global TLS ecosystem. They are not a bulk-download API designed
to absorb arbitrary indexer traffic.

BitsysCerts reads these logs to build a local enrichment index. It does not write to CT
logs, does not affect certificate issuance, and does not impersonate a CT log operator.

---

## How BitsysCerts Accesses CT Logs

The ingestion pipeline is designed to access public CT logs respectfully and sustainably.

### Log discovery

BitsysCerts uses the published CT log list (Google Chrome CT Log Policy list) rather than
hardcoded or user-supplied log URLs. This ensures the ingestion pipeline targets only
currently eligible, active logs.

### Per-log cursors

Every CT log has its own persistent tail cursor stored in `ct_log_tail_cursors`. The
worker only fetches entries beyond the current cursor — it never re-fetches the full log
on restart unless explicitly instructed via `ctpool reset-tail-cursors`.

### Bounded concurrency

Worker concurrency and batch sizes are configurable. The defaults are conservative.
The adaptive batch-size controller (EMA-based) reduces throughput automatically when
database contention is observed. Operators should not set unbounded concurrency without
understanding the impact on the CT log operator's infrastructure.

### Rate-limit handling

The ingestion pipeline honours `Retry-After` headers and backs off with exponential
delay when a CT log returns HTTP 429 (Too Many Requests). It also backs off on server
errors (HTTP 5xx) and connection timeouts. CT log endpoints experiencing issues are
marked as degraded in the operator dashboard.

### Disk and storage awareness

The disk guard monitors available space on the PostgreSQL data mount before each write
cycle. Ingestion halts automatically before the critical threshold is reached, preventing
runaway storage consumption from affecting the host system.

---

## What CT Data Means

> [!IMPORTANT]
> Certificate Transparency data is evidence that a hostname appeared in a publicly logged
> certificate. It is **not** proof that the hostname currently resolves, is reachable, or
> is still operated by the same entity.

CT data and DNS data are separate evidence streams:

| Evidence stream | What it shows |
|---|---|
| CT observation | A hostname appeared in a publicly logged certificate at some point in the past |
| DNS resolution | The hostname currently resolves to an IP address |
| Live TLS inspection | The endpoint currently presents a valid certificate |

BitsysCerts provides CT-derived enrichment. DNS resolution and live TLS inspection are
out of scope and are not performed by BitsysCerts.

---

## Operator Responsibilities

Operators running BitsysCerts accept responsibility for their deployment's behaviour
toward public CT log infrastructure. Specifically:

- **Do not remove rate-limit back-off logic** from the ingestion pipeline.
- **Do not set `CT_MAX_BATCH_SIZE` or worker concurrency to extreme values** without
  understanding the impact on log operators.
- **Tune `CT_BACKFILL_DAYS` to your actual needs.** A 30-day window is the default.
  Setting this to several years on a first run will generate sustained, heavy traffic
  against CT log endpoints.
- **Use the `current-osint` profile** (the default) unless you have a specific reason
  to use `research` or `archive`. Aggressive retention with a long backfill window
  consumes significant resources on both your host and the log endpoints.
- **Monitor your instance** via the operator dashboard. Address failed ranges, audit
  findings, and disk pressure promptly.

> [!WARNING]
> Running a high-concurrency indexer against public CT logs without rate-limit awareness
> is inconsiderate to log operators and the broader CT ecosystem. Please be a good citizen.

---

## Evidence Scope Boundary

BitsysCerts is a CT-layer tool. The following are separate concerns that BitsysCerts
does not address:

- **DNS inventory** — whether a hostname currently resolves
- **Live TLS inspection** — whether an endpoint is currently reachable and presenting
  a valid certificate
- **Ownership verification** — whether the same party that issued a certificate still
  controls the associated infrastructure
- **Real-time alerting** — whether a new certificate has been issued in the last few
  seconds (CT tail lag is best-effort, not guaranteed)

If your workflow requires DNS resolution, live reachability checks, or near-real-time
alerting, those capabilities belong in separate tooling that can consume BitsysCerts'
CT-derived enrichment as one input among several evidence streams.

---

## Reporting CT Log Issues

If you observe a CT log behaving unexpectedly (returning malformed data, consistently
returning errors, or appearing to have been discontinued), report it via:

- The `ctpool doctor` command — performs local health checks and surfaces known issues
- The GitHub issue tracker — if you believe BitsysCerts is not handling a log correctly
- The relevant CT log operator's contact channels — for issues with the log itself

Do not file BitsysCerts issues for problems that originate in CT log infrastructure.
