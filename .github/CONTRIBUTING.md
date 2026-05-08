# Contributing to BitsysCerts

Thank you for considering a contribution. BitsysCerts is a self-hostable Certificate
Transparency intelligence service — contributions that improve its reliability, security,
or usability are welcome.

> [!IMPORTANT]
> Read this document fully before opening an issue or pull request. Following these
> guidelines keeps review fast and keeps the codebase coherent.

---

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [How to Report a Bug](#how-to-report-a-bug)
- [How to Request a Feature or Enhancement](#how-to-request-a-feature-or-enhancement)
- [Development Setup](#development-setup)
- [Branching Strategy](#branching-strategy)
- [Commit Conventions](#commit-conventions)
- [Pull Request Process](#pull-request-process)
- [Testing Requirements](#testing-requirements)
- [Style and Formatting](#style-and-formatting)
- [Security Vulnerabilities](#security-vulnerabilities)

---

## Code of Conduct

This project follows the [Contributor Covenant Code of Conduct](https://www.contributor-covenant.org/version/2/1/code_of_conduct/).
By participating you agree to uphold it. Unacceptable behaviour may result in permanent
exclusion from the project.

---

## How to Report a Bug

Use the **Bug Report** issue template. Include:

- BitsysCerts version / commit SHA
- Environment (Docker Compose, bare metal, OS)
- Steps to reproduce — minimal, exact, reproducible
- What you expected vs. what actually happened
- Relevant logs (redact credentials and personal data)

> [!WARNING]
> Do not include private hostnames, IP addresses, or any data that belongs to a third party
> in issue reports. All issues are public.

---

## How to Request a Feature or Enhancement

Use the **Feature Request** or **Enhancement** issue template, as appropriate.

| Template | Use when |
|---|---|
| Feature Request | Net-new capability not currently present |
| Enhancement | Improving existing behaviour, performance, or UX |

Before filing, check:

1. The issue tracker for duplicates.
2. The [Non-Goals](docs/PRD.md#non-goals) section of the PRD — some things are
   intentionally out of scope.
3. The [AGENTS.md](AGENTS.md) scope guardrails.

---

## Development Setup

### Prerequisites

| Tool | Minimum version |
|---|---|
| Docker + Docker Compose | 24.x / v2 |
| Python | 3.12 |
| Node | 22 |
| PostgreSQL | 17 (via Docker is fine) |

### First-time setup

```bash
# Clone
git clone https://github.com/bitsyscerts/bitsyscerts.git
cd bitsyscerts

# Install Git hooks (ruff, eslint pre-commit checks)
bash src/install-hooks.sh

# Start the full stack
cd src
cp .env.example .env          # edit to set POSTGRES_PASSWORD
docker compose up postgres -d
docker compose run --rm migrate
docker compose up
```

### Running the API in development

```bash
cd src/api
pip install -e ".[dev]"
certsapi serve --reload
```

### Running the frontend in development

```bash
cd src/app
npm install
npm run dev
```

### Running the ingestion workers

```bash
cd src/ctpool
pip install -e ".[dev]"
ctpool sync-logs
ctpool tail --progress
```

---

## Branching Strategy

| Branch | Purpose |
|---|---|
| `main` | Always deployable; protected |
| `feat/<short-description>` | New features |
| `fix/<short-description>` | Bug fixes |
| `chore/<short-description>` | Dependency bumps, tooling, non-functional changes |
| `docs/<short-description>` | Documentation-only changes |

> [!NOTE]
> Branch names use lowercase kebab-case. Keep descriptions short (3–5 words).

---

## Commit Conventions

BitsysCerts uses [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <imperative summary, ≤72 chars>

[optional body — wrap at 72 chars]

[optional footer — BREAKING CHANGE, Closes #NNN]
```

**Types:** `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`, `perf`, `ci`

**Scopes:** `api`, `app`, `ctpool`, `db`, `docker`, `ci`, `docs`

**Examples:**

```
feat(api): add depth filter to hostname search
fix(ctpool): handle HTTP 429 from CT log endpoints
docs(arch): add mermaid data-flow diagram
chore(deps): bump cryptography to 48.0.0
```

> [!NOTE]
> Commits that break the public API MUST include `BREAKING CHANGE:` in the footer.

---

## Pull Request Process

1. **Open an issue first** for non-trivial changes. PRs without a linked issue may be
   closed without review.
2. **One concern per PR.** Mix of features + fixes + refactors = slow review.
3. **Fill the PR template completely.** Incomplete templates will be returned.
4. **Tests must pass.** CI runs `pytest` (Python) and `npm run test` (React).
   Both commands include linting and coverage. A passing CI is a hard requirement.
5. **Coverage gate is 75%.** Every dimension (statements, branches, functions, lines)
   must stay at or above 75% after your changes.
6. **Security.** Non-trivial PRs that touch request handling, authentication, or data
   persistence will receive an OWASP review pass before merge.
7. **At least one approving review** from a maintainer is required before merge.
8. Maintainers squash-merge feature branches; rebase-merge fix and chore branches.

> [!CAUTION]
> Do not force-push to a PR branch after review has started. Open a new PR if the
> direction has changed significantly.

---

## Testing Requirements

All code ships with tests. No exceptions.

| Language | Runner | Command |
|---|---|---|
| Python | pytest | `cd src/api && pytest` or `cd src/ctpool && pytest` |
| TypeScript/React | Vitest | `cd src/app && npm run test` |

**Hard rules:**

- Unit tests live alongside implementation in the same commit.
- 75% coverage on all four dimensions is a hard gate, not a target.
- Test names describe the scenario, not the function name.
  - Bad: `test_search()`
  - Good: `test_hostname_search_returns_empty_list_for_unknown_domain()`
- Every edge case that can be described in a sentence must have a test.

See [.github/instructions/testing.instructions.md](.github/instructions/testing.instructions.md)
for the complete testing standard.

---

## Style and Formatting

Refer to [docs/STYLE_GUIDE.md](docs/STYLE_GUIDE.md) for the full guide. The short version:

| Concern | Tool | Config |
|---|---|---|
| Python formatting | ruff format | `src/api/pyproject.toml`, `src/ctpool/pyproject.toml` |
| Python linting | ruff check | Same |
| Python types | mypy (strict) | Same |
| TypeScript/React | ESLint + Airbnb rules | `src/app/eslint.config.js` |
| TypeScript types | tsc --noEmit | `src/app/tsconfig.json` |

Run formatters before committing:

```bash
# Python
ruff format src/api src/ctpool
ruff check --fix src/api src/ctpool

# TypeScript
cd src/app && npm run lint -- --fix
```

The pre-commit hooks installed by `src/install-hooks.sh` run these automatically.

> [!TIP]
> File size limits are enforced by code review, not tooling. Files over 500 lines are a
> defect and must be split before any other work proceeds.

---

## Security Vulnerabilities

**Do not open a public issue for a security vulnerability.**

Report security issues by emailing **security@bitsyscerts.example** (replace with the
actual contact address set by the project maintainers). You will receive an acknowledgement
within 72 hours.

Include:

- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested remediation (if known)

We follow responsible disclosure: we aim to release a fix within 30 days of a confirmed
report and will credit reporters in the release notes unless anonymity is requested.

> [!WARNING]
> Vulnerabilities that are publicly disclosed without prior notification to the maintainers
> will be treated as out of policy. We reserve the right not to issue a CVE in such cases.
