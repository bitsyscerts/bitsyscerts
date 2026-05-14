# bitsyscerts — Project-Wide Coding Mandates

This is a GitHub repository first. The repository root is reserved exclusively for repository
metadata. These rules are non-negotiable and apply to every contributor — human or AI.

---

## Repository Root: Metadata Only

The following are the ONLY files and directories permitted at the repository root:

- `README.md`
- `AGENTS.md`
- `INITIAL_PLAN.md`
- `.github/`
- `.gitignore`
- `LICENSE`
- `.editorconfig`

**MUST NOT** create source files, configuration files, `package.json`, `pyproject.toml`,
`vite.config.ts`, `tsconfig.json`, `requirements.txt`, `Dockerfile`, or any tool configuration
at the repository root. Every such file belongs inside `src/` or a sub-project directory within
it. If you are about to create a file at the repo root that is not in the list above, stop and
place it under `src/`.

---

## Monorepo Structure

```
src/
  api/          # Python · FastAPI · PostgreSQL backend
  app/          # React · Vite · Mantine frontend
```

Each sub-project has its own `AGENTS.md` with additional domain-specific rules that extend and
refine these mandates. Sub-project `AGENTS.md` files are authoritative for their directory; this
root file is authoritative for the repository as a whole.

---

## Core Principles

All four principles below are mandatory. Violating any one of them is a **defect**, not a style
preference. Do not rationalize exceptions.

---

### 1 · src/ Is the Technical Root

Every source file, configuration file, toolchain config, and dependency manifest lives inside
`src/`. There are no exceptions.

```
WRONG:  /package.json          ← repo root
WRONG:  /pyproject.toml        ← repo root
WRONG:  /vite.config.ts        ← repo root
CORRECT: src/app/package.json
CORRECT: src/api/pyproject.toml
CORRECT: src/app/vite.config.ts
```

---

### 2 · Decomposition First — No Monolithic Files

Before writing any implementation code, decompose the problem into its smallest independently
testable units. Building a large block of code first and extracting later is **not acceptable**.

**File size limits (Robert C. Martin, *Clean Code*):**

| Lines      | Status                                                                  |
|------------|-------------------------------------------------------------------------|
| ≤ 200      | Good — the preferred target for all files                               |
| 201 – 500  | Warning — MUST add a comment block at the top of the file explaining why consolidation is justified and when it will be resolved |
| > 500      | Defect — MUST split the file immediately before any other work proceeds |

**Function/method size limits (Robert C. Martin, *Clean Code*):**

| Lines  | Status                                                                              |
|--------|-------------------------------------------------------------------------------------|
| ≤ 20   | Good — the preferred target for all functions and methods                           |
| 21–50  | Warning — MUST add an inline comment explaining why extraction is not yet possible  |
| > 50   | Defect — MUST split the function before proceeding with any other work              |

**Additional decomposition rules:**

- Every module, class, and component has exactly **one** responsibility (Single Responsibility
  Principle). If you need the word "and" to describe its purpose, it has too many.
- Build **leaves first**. Compound objects are assembled from proven, tested components. Writing
  top-down — page before component, component before hook, service before utility — is prohibited.
- If a concept could be independently unit tested, it MUST be its own module, class, or component.

See [decomposition.instructions.md](.github/instructions/decomposition.instructions.md) for the
full ruleset, which is always active for all files under `src/`.

---

### 3 · Best Practices, Security-First, and Consistent Formatting

- All code follows the canonical style guide for its language: PEP-8 for Python, React + Airbnb
  rules for TypeScript/TSX.
- Linting and formatting MUST pass before any code is considered complete. Code that does not
  pass the linter is not finished code.
- **After every edit to a Python file**, run `ruff check --fix` then `ruff format` then confirm
  `ruff check` is clean — in that order — before calling the task complete. This MUST happen
  even for one-line changes. The single most common pre-commit failure is I001 (unsorted
  imports); it is always auto-fixable and is never an acceptable reason to hand back broken
  code. See [python.instructions.md](.github/instructions/python.instructions.md) for the
  exact commands.
- Security is a design constraint applied from line one — not a review step added afterward.
  Threat model every feature. Validate all inputs at system boundaries. Encode all outputs.
  MUST comply with OWASP Top 10 (2021) and OWASP API Top 10 (2023) on every endpoint and
  component that handles user data.

See [security.instructions.md](.github/instructions/security.instructions.md) for the full
checklist, which is always active for all files under `src/`.

---

### 4 · Tests Ship With Code — No Exceptions

- Unit tests are written alongside implementation in the same commit/PR — not after, not "soon."
- Code coverage MUST reach **75% on all four dimensions** (statements, branches, functions,
  lines) or the feature does not ship. This is a hard gate, not a target.
- Every edge case is explicitly named in a test. Test names MUST describe the scenario being
  tested, not just the function name.
- The unified test command includes linting: `pytest` (Python) and `npm run test` (React) each
  fail if linting fails. A green test run with linting disabled is not a green test run.

See [testing.instructions.md](.github/instructions/testing.instructions.md) for the full
standard.

---

## Scope and Retention Guardrails

BitsysCerts is a **current, query-oriented** CT intelligence service — not a full historical
mirror of the public CT ecosystem. Every contributor (human or AI) must apply these guardrails
when designing schemas, writing ingestion code, building API endpoints, or modifying retention
logic. Violating them is a **defect**.

### What BitsysCerts is

Describe BitsysCerts in documentation and comments as:

> A self-hostable Certificate Transparency intelligence service for current hostname discovery,
> certificate metadata lookup, and OSINT pivot support.

Do **not** describe BitsysCerts as a complete CT mirror, a full replacement for every
historical `crt.sh` use case, a complete archive of all public certificates, or a permanent
copy of all CT log data.

### Default retention mode: `current-osint`

The default retention mode is `current-osint`. All code must be written to honour this default.

| Guardrail | Requirement |
|---|---|
| No unbounded tables by accident | Every table that grows from CT ingestion MUST have a documented retention policy |
| No raw-data retention by default | Full raw certificates, chains, and raw CT responses MUST be optional and time-bounded |
| Separate current state from observations | Durable hostname state and bounded certificate observations MUST be separate |
| Deduplicate aggressively | Use certificate fingerprint, hostname, registered domain, and log source to reduce redundancy |
| Make retention configurable | Retention windows MUST be configurable via environment variables or deployment config |
| Expose storage metrics | The application MUST expose row-count / storage metrics by table |
| Fail retention jobs safely | Retention job failures MUST surface through logs and health/status endpoints |
| Document profile impact | Each retention profile MUST clearly state expected storage implications |

### Retention profiles

| Profile | Default? | Storage class | Notes |
|---|---|---|---|
| `current-osint` | **Yes** | GB-class | Fresh OSINT and hostname discovery; bounded rolling windows |
| `research` | No | GB–TB-class | Longer lookback; richer metadata; still not a full archive |
| `archive` | **Never** | TB-class or multi-TB | Full CT archival; must require explicit opt-in configuration |

The `archive` profile MUST never be activated by default. Code that enables archive-mode
behavior without explicit configuration is a defect.

### Non-goals (enforced)

Do not implement the following without an explicit architectural decision record:

- Mirroring every CT log forever.
- Retaining every certificate ever observed.
- Retaining every duplicate CT log entry.
- Storing full public key material by default.
- Reconstructing the full historical certificate state of the internet.
- Becoming a general-purpose internet archive.

### Integration boundary rule

BitsysCerts provides CT intelligence. It does not absorb BitsysTools or BitsysTrace
functionality. Any feature that belongs in a consumer project MUST be rejected.

---

## Detailed Rules by Concern

| File | Trigger | Covers |
|------|---------|--------|
| [decomposition.instructions.md](.github/instructions/decomposition.instructions.md) | Always active for `src/**` | Component decomposition, file/function size limits, naming, build order |
| [security.instructions.md](.github/instructions/security.instructions.md) | Always active for `src/**` | OWASP Top 10, OWASP API Top 10, input validation, output encoding, secrets |
| [python.instructions.md](.github/instructions/python.instructions.md) | Active for `**/*.py` | PEP-8, type hints, FastAPI patterns, async, package structure |
| [react.instructions.md](.github/instructions/react.instructions.md) | Active for `**/*.tsx`, `**/*.ts` | React Rules of Hooks, Error Boundaries, Suspense, Mantine, accessibility |
| [testing.instructions.md](.github/instructions/testing.instructions.md) | On-demand | pytest, Vitest, coverage thresholds, edge case requirements |

---

## Prompts and Agents

Use the following workflows for common tasks. Do not bypass them.

| Slash Command | Purpose |
|---------------|---------|
| `/new-feature-workflow` | Start any new feature — enforces decomposition plan before code |
| `/new-python-module` | Scaffold a Python package/module with tests |
| `/new-react-component` | Scaffold a React component with Error Boundary and tests |
| `/new-api-endpoint` | Scaffold a FastAPI endpoint with validation, auth, and tests |
| `/security-review` | OWASP audit of any file or module |

The **Planner** agent produces decomposition plans. The **Security Auditor** agent performs OWASP
reviews. Both are read-only — they do not write code.
