# BitsysCerts — Workspace Copilot Instructions

BitsysCerts is a self-hostable Certificate Transparency (CT) intelligence service for current
hostname discovery, certificate metadata lookup, and OSINT pivot support. It is NOT a full CT
archive. Default retention mode is `current-osint`.

## Sub-project Layout

| Path          | Language / Stack                                 | Purpose                       |
| ------------- | ------------------------------------------------ | ----------------------------- |
| `src/api/`    | Python · FastAPI · SQLAlchemy async · PostgreSQL | REST API                      |
| `src/app/`    | TypeScript · React · Vite · Mantine              | Frontend SPA                  |
| `src/ctpool/` | Python · Click CLI · SQLAlchemy async · Alembic  | CT ingestion workers + schema |

**Repository root** is metadata-only (`README.md`, `AGENTS.md`, `LICENSE`, `.github/`, `.gitignore`, `.editorconfig`). All source, config, and tooling lives under `src/`.

## Non-Negotiable Constraints

1. **Every new DB table must declare a retention policy.** No table may grow unboundedly from
   CT ingestion without a documented and implemented prune strategy.
2. **The `archive` retention profile must never be the default.** Default is `current-osint`.
3. **Python: run `ruff check --fix` then `ruff format` then `ruff check` (zero violations)
   after every `.py` edit.** See `.github/instructions/python.instructions.md` for exact commands.
4. **React: run `npm run test` (lint + typecheck + vitest + coverage) after every `.tsx`/`.ts`
   edit.** `npm run test:coverage` runs vitest only — use `npm run test` for full validation.
5. **75% coverage is a hard gate on all four dimensions.** Features do not ship below it.
6. **No source file exceeds 200 lines. No function exceeds 20 lines.** Split immediately.
7. **OWASP Top 10 (2021) and OWASP API Top 10 (2023) compliance is required** on every
   endpoint and component that handles user data.

## Always-Active Instruction Files

These files refine behavior for specific file types — read them before editing:

| Instruction                                                | Applies To                        |
| ---------------------------------------------------------- | --------------------------------- |
| `.github/instructions/decomposition.instructions.md`       | All `src/**`                      |
| `.github/instructions/security.instructions.md`            | All `src/**`                      |
| `.github/instructions/retention.instructions.md`           | All `src/**`                      |
| `.github/instructions/python.instructions.md`              | All `*.py`                        |
| `.github/instructions/database.instructions.md`            | Migrations, models, DB access     |
| `.github/instructions/react.instructions.md`               | `src/app/**`                      |
| `.github/instructions/testing.instructions.md`             | All `src/**`                      |
| `.github/instructions/git-usage.instructions.md`           | All `src/**` · git/gh ops         |
| `.github/instructions/update-dependencies.instructions.md` | `src/**` · `.github/workflows/**` |

## Virtualenv

```bash
source /workspaces/bitsyscerts/.venv/bin/activate
```

Both `src/api/` and `src/ctpool/` are installed into this virtualenv.
