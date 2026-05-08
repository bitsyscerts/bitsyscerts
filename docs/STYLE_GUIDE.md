# BitsysCerts Style Guide

This guide is the authoritative reference for code style across all sub-projects. It
summarises the automated tooling configurations and adds conventions not covered by linters.
When in doubt, prefer readability over cleverness.

> [!NOTE]
> Automated linters and formatters are the first line of enforcement. This document covers
> intent and the areas tooling cannot catch.

---

## Table of Contents

- [General Principles](#general-principles)
- [File and Function Size Limits](#file-and-function-size-limits)
- [Python (src/api, src/ctpool)](#python-srcapi-srcctpool)
- [TypeScript and React (src/app)](#typescript-and-react-srcapp)
- [SQL and Database Conventions](#sql-and-database-conventions)
- [Git Commit Style](#git-commit-style)
- [Documentation Style](#documentation-style)

---

## General Principles

1. **Clarity over brevity.** A name that requires no comment beats a name with one.
2. **One responsibility per unit.** If you need "and" to describe a function's purpose,
   split it.
3. **Build leaves first.** Prove small units correct before composing them.
4. **No magic numbers.** Every constant that carries meaning gets a named binding.
5. **Fail loudly at boundaries, silently never.** Validate all external input. Do not
   swallow exceptions.

---

## File and Function Size Limits

These are hard limits, not suggestions. Violations are defects.

### Files

| Lines | Status |
|---|---|
| ≤ 200 | Good — preferred target |
| 201 – 500 | Warning — add a top-of-file comment explaining why and when it will be resolved |
| > 500 | **Defect — split before any other work proceeds** |

### Functions and Methods

| Lines | Status |
|---|---|
| ≤ 20 | Good — preferred target |
| 21 – 50 | Warning — add an inline comment explaining why extraction is not yet possible |
| > 50 | **Defect — split before proceeding** |

---

## Python (`src/api`, `src/ctpool`)

### Formatter and Linter

- **Formatter:** `ruff format` (line length 88, matches Black)
- **Linter:** `ruff check` with rule sets: `E`, `F`, `I`, `N`, `W`, `UP`, `S`, `B`, `A`,
  `C4`, `PTH`
- **Type checker:** `mypy` in strict mode

Run before every commit:

```bash
ruff format src/api src/ctpool
ruff check --fix src/api src/ctpool
mypy src/api/certsapi src/ctpool/ctpool
```

### Type Hints

Every function and method signature must carry complete type hints. No `Any` unless
unavoidable, and even then the usage must be commented.

```python
# Good
async def get_hostnames(params: HostnameSearchParams, db: AsyncSession) -> HostnameListResponse:
    ...

# Bad — missing return type, missing parameter types
async def get_hostnames(params, db):
    ...
```

### Naming

| Element | Convention | Example |
|---|---|---|
| Modules | `snake_case` | `cert_writer.py` |
| Classes | `PascalCase` | `BackfillWorker` |
| Functions/methods | `snake_case` | `parse_san_list()` |
| Constants | `UPPER_SNAKE_CASE` | `DEFAULT_BATCH_SIZE` |
| Type aliases | `PascalCase` | `FingerprintSha256 = str` |
| Private members | `_leading_underscore` | `_build_query()` |

### Docstrings

Every public module, class, and function must have a docstring. Use the Google style:

```python
def search_hostnames(q: str, limit: int) -> list[HostnameResult]:
    """Return hostnames matching the given query string.

    Args:
        q: Search query. Supports exact match, ``*.domain`` wildcard,
           and ``re:pattern`` regex syntax.
        limit: Maximum number of results to return. Must be 1–200.

    Returns:
        A list of matching HostnameResult objects, ordered by last_seen_ct desc.

    Raises:
        InvalidQueryError: If the query syntax is not recognised.
    """
```

### Async

- All I/O is async. No synchronous database or HTTP calls in the hot path.
- Use `async with` for database sessions; never hold a session across a `yield` in a
  non-generator context.
- Prefer `asyncio.gather()` for independent concurrent operations over sequential awaits.

### Imports

Imports are grouped and ordered by `ruff` (isort-compatible):

1. Standard library
2. Third-party
3. Local (`from certsapi.` or `from ctpool.`)

No wildcard imports (`from module import *`).

### Error Handling

- Raise specific exception types. Do not raise bare `Exception`.
- Catch the narrowest exception type possible.
- Log with context before re-raising:
  ```python
  except httpx.TimeoutException as exc:
      logger.warning("CT log request timed out", url=log_url, exc_info=exc)
      raise
  ```
- Never silence exceptions in production code paths (`except Exception: pass` is a defect).

### Security (Python)

- **No f-strings in SQL.** Always use parameterised queries via SQLAlchemy.
- **No `eval()` or `exec()`.**
- **Secrets come from environment variables via `pydantic-settings`.** Never hardcode
  credentials.
- **Validate all external data** (CT log responses, query parameters) with Pydantic before
  use.

---

## TypeScript and React (`src/app`)

### Formatter and Linter

- **Linter:** ESLint with `@typescript-eslint` and Airbnb rules (see `eslint.config.js`)
- **Type checker:** `tsc --noEmit`

Run before every commit:

```bash
cd src/app
npm run lint -- --fix
npx tsc --noEmit
```

### TypeScript Conventions

- **Strict mode is on.** No `any` types. Use `unknown` and narrow it.
- **Interfaces over type aliases** for object shapes; type aliases for unions and primitives.
- **Explicit return types** on all exported functions and hooks.
- **No non-null assertions** (`!`) except in tests.

```typescript
// Good
interface HostnameResult {
  id: string;
  hostname: string;
  registrable_domain: string;
}

// Bad — using type for an object shape
type HostnameResult = {
  id: string;
  hostname: string;
};
```

### Naming

| Element | Convention | Example |
|---|---|---|
| Components | `PascalCase` | `SearchBox` |
| Hooks | `camelCase` prefixed with `use` | `usePaginatedSearch` |
| Context | `PascalCase` + `Context` suffix | `SearchStateContext` |
| Types/Interfaces | `PascalCase` | `HostnameSearchParams` |
| Constants | `UPPER_SNAKE_CASE` | `DEFAULT_LIMIT` |
| Event handlers | `handle` prefix | `handleSubmit` |
| Boolean props | `is` / `has` / `can` prefix | `isLoading`, `hasError` |

### React Rules

- **Hooks obey the Rules of Hooks.** No conditional hook calls. ESLint enforces this.
- **Every page component is wrapped in an `ErrorBoundary`.**
- **Async data always uses TanStack Query** (`useQuery`, `useMutation`) — not raw `fetch` or
  `useEffect` for data fetching.
- **No prop drilling beyond two levels.** Use Context or extract a custom hook.
- **Mantine components and theme tokens** must be used for all UI. No hardcoded colours,
  spacing, or font sizes.
- **Accessibility:** interactive elements must have accessible names (ARIA labels if no
  visible text). Use semantic HTML (`<button>`, `<nav>`, `<main>`, `<section>`).

### Component Size

- One component per file.
- Component functions must stay under 50 lines (see [Function size limits](#file-and-function-size-limits)).
  Split large render trees into named sub-components.
- Extract non-rendering logic to custom hooks.

### File Structure

```
src/
  components/
    ComponentName/
      index.tsx          ← public export
      ComponentName.tsx  ← implementation
      ComponentName.test.tsx
  hooks/
    useHookName.ts
    useHookName.test.ts
  pages/
    PageName/
      index.tsx
      PageName.tsx
      PageName.test.tsx
```

---

## SQL and Database Conventions

- All table names are `snake_case` plural: `certificates`, `hostnames`, `ct_log_sources`.
- All column names are `snake_case`.
- Foreign key columns are named `<referenced_table_singular>_id`.
- Indexes are named `ix_<table>_<columns>`.
- Unique constraints are named `uq_<table>_<columns>`.
- Every migration file has a descriptive message in its filename.
- Migrations are irreversible in production. Downgrade paths must be tested locally before
  being considered safe.
- **Never drop a column in the same migration that removes references to it.** Two-phase
  (add-then-remove) deploys are safer.

---

## Git Commit Style

See [CONTRIBUTING.md — Commit Conventions](CONTRIBUTING.md#commit-conventions) for the
full Conventional Commits reference.

Quick rules:

- Imperative mood in summary: "add", "fix", "remove" — not "added", "fixes", "removed".
- Summary line ≤ 72 characters.
- Body wraps at 72 characters.
- One logical change per commit. Squash "WIP" and "fix typo" commits before opening a PR.

---

## Documentation Style

All Markdown documentation uses GitHub Flavored Markdown (GHFM).

### Admonitions

Use GitHub's alert syntax for callouts:

```markdown
> [!NOTE]
> Informational detail that helps understanding.

> [!TIP]
> Optional advice that can improve the reader's workflow.

> [!IMPORTANT]
> Critical information required to proceed correctly.

> [!WARNING]
> Potentially harmful consequence if ignored.

> [!CAUTION]
> Risk of data loss, security issue, or irreversible action.
```

### Diagrams

Use Mermaid for all architecture, flow, and sequence diagrams. Wrap in a fenced code block:

````markdown
```mermaid
flowchart LR
    A --> B
```
````

### Headings

- `#` — Document title only (one per document)
- `##` — Major sections
- `###` — Sub-sections
- `####` — Rarely needed; prefer restructuring over deep nesting

### Tables

Use GFM tables for structured comparisons. Align pipes for readability in source:

```markdown
| Column A | Column B | Column C |
|---|---|---|
| value    | value    | value    |
```
